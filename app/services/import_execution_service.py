"""
Phase 3.2D-MVP — Import Execution Engine. Commits ONE session's already-
validated preview to the real catalog: creates missing Suppliers, creates
or updates Products, creates alternate-supplier SupplierProductOffers.

Every actual write goes through CatalogService's existing validated,
audited methods — this service never touches Product/Supplier/
SupplierProductOffer directly. That's deliberate: CatalogService is
already the single, tested, audited path every other part of the app
writes catalog changes through, so reusing it here means Import Execution
inherits its whitelist validation and audit logging for free instead of
duplicating (and potentially diverging from) it.

All-or-nothing: this whole commit is one transaction (the route commits
once, at the end, per this app's "commits only in Routes" convention). If
anything raises, nothing persists. Rollback (for an ALREADY-committed
execution) is a separate, explicit action — see rollback() below.
"""
from decimal import Decimal
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_mapping_repository import ImportMappingRepository
from app.repositories.import_validation_repository import ImportValidationRepository, ImportPreviewRepository
from app.repositories.import_execution_repository import ImportExecutionRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_offer_repository import SupplierOfferRepository
from app.models.import_mapping import MAPPING_STATUS_APPROVED
from app.models.import_validation import VALIDATION_STATUS_COMPLETED, ACTION_CREATE, ACTION_UPDATE
from app.models.import_execution import EXECUTION_STATUS_COMMITTED, EXECUTION_STATUS_ROLLED_BACK
from app.services.catalog_service import CatalogService
from app.services.audit_service import AuditService


class ImportExecutionError(Exception):
    """Raised when a commit/rollback can't proceed at all (not approved,
    not validated, already committed, nothing to roll back, etc.)."""


class ImportExecutionService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_repo = ImportSessionRepository(tenant_id)
        self.mapping_repo = ImportMappingRepository(tenant_id)
        self.validation_repo = ImportValidationRepository(tenant_id)
        self.preview_repo = ImportPreviewRepository(tenant_id)
        self.execution_repo = ImportExecutionRepository(tenant_id)
        self.product_repo = ProductRepository(tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id)
        self.offer_repo = SupplierOfferRepository(tenant_id)
        self.catalog_service = CatalogService(tenant_id, user_id)

    def get_latest_execution(self, session_id: int):
        self.session_repo.get_by_id_or_404(session_id)  # tenant ownership check
        return self.execution_repo.get_latest_by_session(session_id)

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------
    def commit(self, session_id: int):
        session = self.session_repo.get_by_id_or_404(session_id)

        mapping = self.mapping_repo.get_by_session_and_sheet(session_id, session.staged_sheet_name)
        if not mapping or mapping.status != MAPPING_STATUS_APPROVED:
            raise ImportExecutionError("The mapping must be approved before committing.")

        validation = self.validation_repo.get_latest_by_session(session_id)
        if not validation or validation.status != VALIDATION_STATUS_COMPLETED:
            raise ImportExecutionError("Validation must complete successfully before committing.")

        previous = self.execution_repo.get_latest_by_session(session_id)
        if previous and previous.status == EXECUTION_STATUS_COMMITTED:
            raise ImportExecutionError(
                "This session was already imported. Roll back the previous execution first if you want to re-run it."
            )

        # Snapshot — counts taken right before any write, for a clear
        # before/after in the summary.
        snapshot_suppliers = len(self.supplier_repo.get_all_for_matching())
        snapshot_products = len(self.product_repo.get_all_for_matching())
        snapshot_offers = self.offer_repo.count_all()

        rows = self.preview_repo.get_all_by_validation(validation.id)

        supplier_cache = {
            s.name.strip().lower(): s.id for s in self.supplier_repo.get_all_for_matching()
        }
        created_supplier_ids = []
        created_product_ids = []
        created_offer_ids = []
        price_history = []
        skipped_rows = []
        products_created = 0
        products_updated = 0

        def resolve_or_create_supplier(name: str):
            key = name.strip().lower()
            if key in supplier_cache:
                return supplier_cache[key]
            supplier = self.catalog_service.create_supplier({"name": name.strip()})
            supplier_cache[key] = supplier.id
            created_supplier_ids.append(supplier.id)
            return supplier.id

        for row in rows:
            if row.has_errors or row.product_action not in (ACTION_CREATE, ACTION_UPDATE):
                continue

            try:
                if row.product_action == ACTION_CREATE:
                    if not row.supplier_name and not row.matched_supplier_id:
                        skipped_rows.append({
                            "row_number": row.row_number,
                            "reason": "No supplier could be determined for this row (should have been caught by validation).",
                        })
                        continue
                    supplier_id = row.matched_supplier_id or resolve_or_create_supplier(row.supplier_name)
                    product_data = {
                        "supplier_id": supplier_id,
                        "name": row.product_name,
                        "current_price": float(row.price),
                    }
                    if row.unit:
                        product_data["unit"] = row.unit
                    if row.category:
                        product_data["category"] = row.category
                    product = self.catalog_service.create_product(product_data)
                    created_product_ids.append(product.id)
                    products_created += 1
                else:  # ACTION_UPDATE
                    # Price-only by design: an existing product's unit/
                    # category may have been curated by hand since it was
                    # first created — importing a new price for it
                    # shouldn't silently overwrite those.
                    product = self.catalog_service.update_product(row.matched_product_id, {
                        "current_price": float(row.price),
                    })
                    price_history.append({
                        "product_id": product.id,
                        "old_price": float(row.old_price) if row.old_price is not None else None,
                        "new_price": float(row.price),
                    })
                    products_updated += 1

                # Alternate-supplier offers (WIDE format) — every offer
                # column EXCEPT the one already used as this product's
                # primary listing (same supplier+price the row itself used).
                for offer in (row.offers or []):
                    is_primary = (
                        offer["supplier_name"] == row.supplier_name
                        and offer["price"] == float(row.price)
                    )
                    if is_primary:
                        continue
                    try:
                        offer_supplier_id = offer["matched_supplier_id"] or resolve_or_create_supplier(offer["supplier_name"])
                        created_offer = self.catalog_service.create_offer(product.id, {
                            "supplier_id": offer_supplier_id,
                            "price": offer["price"],
                        })
                        created_offer_ids.append(created_offer.id)
                    except (BadRequest, Conflict) as exc:
                        # Benign, expected edge cases (e.g. this supplier
                        # already has a price on file from an earlier row
                        # in this same commit) — not fatal to the row.
                        skipped_rows.append({
                            "row_number": row.row_number,
                            "reason": f'Offer for "{offer["supplier_name"]}" skipped: {exc.description}',
                        })

            except (BadRequest, Conflict, NotFound) as exc:
                skipped_rows.append({"row_number": row.row_number, "reason": str(exc.description or exc)})
                continue

        execution = self.execution_repo.model(
            tenant_id=self.tenant_id,
            import_session_id=session_id,
            import_validation_id=validation.id,
            status=EXECUTION_STATUS_COMMITTED,
            snapshot_suppliers_before=snapshot_suppliers,
            snapshot_products_before=snapshot_products,
            snapshot_offers_before=snapshot_offers,
            suppliers_created=len(created_supplier_ids),
            products_created=products_created,
            products_updated=products_updated,
            offers_created=len(created_offer_ids),
            created_supplier_ids=created_supplier_ids,
            created_product_ids=created_product_ids,
            created_offer_ids=created_offer_ids,
            price_history=price_history,
            skipped_rows=skipped_rows,
            executed_by=self.user_id,
        )
        self.execution_repo.add(execution)

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.committed",
            f"Committed {session.filename} ({session.staged_sheet_name}): "
            f"{len(created_supplier_ids)} supplier(s), {products_created} product(s) created, "
            f"{products_updated} updated, {len(created_offer_ids)} offer(s) created",
            {
                "import_session_id": session_id, "import_execution_id": execution.id,
                "suppliers_created": len(created_supplier_ids), "products_created": products_created,
                "products_updated": products_updated, "offers_created": len(created_offer_ids),
                "skipped_row_count": len(skipped_rows),
            },
        )
        return execution

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------
    def rollback(self, execution_id: int):
        execution = self.execution_repo.get_by_id_or_404(execution_id)
        if execution.status == EXECUTION_STATUS_ROLLED_BACK:
            raise ImportExecutionError("This execution has already been rolled back.")

        # Offers first (Product's own cascade would also remove them, but
        # being explicit keeps the audit trail per-offer and doesn't rely
        # on cascade ordering for correctness).
        for offer_id in execution.created_offer_ids:
            offer = self.offer_repo.get_by_id(offer_id)
            if offer is not None:
                self.offer_repo.delete(offer)

        # Restore updated products' prices BEFORE deleting created ones —
        # unrelated operations, order doesn't matter between them, but
        # keeping price restoration first makes a partial-failure state
        # easier to reason about (prices are back to normal even if a
        # delete below hits something unexpected).
        for entry in execution.price_history:
            product = self.product_repo.get_by_id(entry["product_id"])
            if product is not None and entry["old_price"] is not None:
                self.catalog_service.update_product(product.id, {"current_price": entry["old_price"]})

        for product_id in execution.created_product_ids:
            product = self.product_repo.get_by_id(product_id)
            if product is not None:
                self.catalog_service.delete_product(product_id)

        for supplier_id in execution.created_supplier_ids:
            supplier = self.supplier_repo.get_by_id(supplier_id)
            if supplier is None:
                continue
            # Only remove a supplier we created if it's not left owning
            # anything else in the meantime — safe default, never delete
            # data this rollback didn't itself create.
            if not self.product_repo.get_by_supplier(supplier_id) and not supplier.offered_products:
                self.supplier_repo.delete(supplier)

        from datetime import datetime, timezone
        execution.status = EXECUTION_STATUS_ROLLED_BACK
        execution.rolled_back_by = self.user_id
        execution.rolled_back_at = datetime.now(timezone.utc)

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.rolled_back",
            f"Rolled back import execution #{execution.id}",
            {"import_execution_id": execution.id, "import_session_id": execution.import_session_id},
        )
        return execution
