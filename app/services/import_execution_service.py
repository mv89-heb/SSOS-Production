"""Phase 3.2D — Import execution engine.

The execution boundary is intentionally fail-closed: validation must be
complete, the mapping must be approved, and every catalog mutation in an
execution must succeed. The service never intentionally leaves a partially
imported transaction behind.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_mapping_repository import ImportMappingRepository
from app.repositories.import_validation_repository import (
    ImportValidationRepository,
    ImportPreviewRepository,
)
from app.repositories.import_execution_repository import ImportExecutionRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_offer_repository import SupplierOfferRepository
from app.models.import_session import ImportSession
from app.models.import_execution import (
    ImportExecution,
    EXECUTION_STATUS_COMMITTED,
    EXECUTION_STATUS_ROLLED_BACK,
)
from app.models.import_mapping import MAPPING_STATUS_APPROVED
from app.models.import_validation import VALIDATION_STATUS_COMPLETED, ACTION_CREATE, ACTION_UPDATE
from app.services.catalog_service import CatalogService
from app.services.audit_service import AuditService


class ImportExecutionError(Exception):
    """Raised when an import cannot safely be committed or rolled back."""


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
        self.session_repo.get_by_id_or_404(session_id)
        return self.execution_repo.get_latest_by_session(session_id)

    def _lock_session(self, session_id: int):
        """Serialize commit attempts for one import session."""
        stmt = (
            select(ImportSession)
            .where(
                ImportSession.id == session_id,
                ImportSession.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        session = db.session.execute(stmt).scalar_one_or_none()
        if session is None:
            raise NotFound("Import session not found")
        return session

    def _lock_execution(self, execution_id: int):
        """Serialize rollback attempts for one execution."""
        stmt = (
            select(ImportExecution)
            .where(
                ImportExecution.id == execution_id,
                ImportExecution.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        execution = db.session.execute(stmt).scalar_one_or_none()
        if execution is None:
            raise NotFound("Import execution not found")
        return execution

    def _fail_transaction(self, message: str):
        """Clear every uncommitted catalog mutation before returning failure."""
        db.session.rollback()
        raise ImportExecutionError(message)

    def commit(self, session_id: int):
        # The row lock is acquired before checking whether an execution already
        # exists. Concurrent requests for the same session therefore serialize
        # instead of both passing the preflight check and importing twice.
        session = self._lock_session(session_id)

        if not session.staged_sheet_name:
            raise ImportExecutionError("This import session has no staged sheet.")

        mapping = self.mapping_repo.get_by_session_and_sheet(
            session_id, session.staged_sheet_name
        )
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

        rows = self.preview_repo.get_all_by_validation(validation.id)
        if not rows:
            raise ImportExecutionError("Validation produced no importable rows.")

        invalid_rows = [r.row_number for r in rows if r.has_errors]
        if invalid_rows:
            raise ImportExecutionError(
                "Import cannot start because validation contains errors in row(s): "
                + ", ".join(str(n) for n in invalid_rows[:20])
            )

        unsupported_rows = [
            r.row_number
            for r in rows
            if r.product_action not in (ACTION_CREATE, ACTION_UPDATE)
        ]
        if unsupported_rows:
            raise ImportExecutionError(
                "Import cannot start because validation contains non-importable row(s): "
                + ", ".join(str(n) for n in unsupported_rows[:20])
            )

        snapshot_suppliers = len(self.supplier_repo.get_all_for_matching())
        snapshot_products = len(self.product_repo.get_all_for_matching())
        snapshot_offers = self.offer_repo.count_all()

        supplier_cache = {
            s.name.strip().lower(): s.id
            for s in self.supplier_repo.get_all_for_matching()
        }
        created_supplier_ids = []
        created_product_ids = []
        created_offer_ids = []
        price_history = []
        products_created = 0
        products_updated = 0

        def resolve_or_create_supplier(name: str):
            if not isinstance(name, str) or not name.strip():
                raise ImportExecutionError("A supplier name is required before creating a supplier.")
            key = name.strip().lower()
            if key in supplier_cache:
                return supplier_cache[key]
            supplier = self.catalog_service.create_supplier({"name": name.strip()})
            supplier_cache[key] = supplier.id
            created_supplier_ids.append(supplier.id)
            return supplier.id

        try:
            for row in rows:
                if row.product_action == ACTION_CREATE:
                    if not row.supplier_name and not row.matched_supplier_id:
                        raise ImportExecutionError(
                            f"Row {row.row_number}: no supplier could be determined."
                        )

                    supplier_id = row.matched_supplier_id or resolve_or_create_supplier(row.supplier_name)
                    if row.price is None:
                        raise ImportExecutionError(f"Row {row.row_number}: price is missing.")

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
                else:
                    if not row.matched_product_id:
                        raise ImportExecutionError(
                            f"Row {row.row_number}: update action has no matched product."
                        )
                    if row.price is None:
                        raise ImportExecutionError(f"Row {row.row_number}: price is missing.")

                    product = self.catalog_service.update_product(
                        row.matched_product_id,
                        {"current_price": float(row.price)},
                    )
                    price_history.append(
                        {
                            "product_id": product.id,
                            "old_price": float(row.old_price) if row.old_price is not None else None,
                            "new_price": float(row.price),
                        }
                    )
                    products_updated += 1

                for offer in row.offers or []:
                    if not isinstance(offer, dict):
                        raise ImportExecutionError(
                            f"Row {row.row_number}: malformed supplier offer data."
                        )
                    supplier_name = offer.get("supplier_name")
                    offer_price = offer.get("price")
                    if not isinstance(supplier_name, str) or not supplier_name.strip():
                        raise ImportExecutionError(
                            f"Row {row.row_number}: supplier offer is missing a supplier name."
                        )
                    if offer_price is None:
                        raise ImportExecutionError(
                            f"Row {row.row_number}: supplier offer is missing a price."
                        )

                    is_primary = (
                        supplier_name.strip().lower() == (row.supplier_name or "").strip().lower()
                        and float(offer_price) == float(row.price)
                    )
                    if is_primary:
                        continue

                    offer_supplier_id = (
                        offer.get("matched_supplier_id")
                        or resolve_or_create_supplier(supplier_name)
                    )
                    try:
                        created_offer = self.catalog_service.create_offer(
                            product.id,
                            {"supplier_id": offer_supplier_id, "price": offer_price},
                        )
                    except (BadRequest, Conflict) as exc:
                        description = getattr(exc, "description", None) or str(exc)
                        raise ImportExecutionError(
                            f'Row {row.row_number}: supplier offer for "{supplier_name}" could not be created: {description}'
                        ) from exc
                    created_offer_ids.append(created_offer.id)

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
                skipped_rows=[],
                executed_by=self.user_id,
            )
            self.execution_repo.add(execution)

            AuditService.log_event(
                self.tenant_id,
                self.user_id,
                "import.committed",
                f"Committed {session.filename} ({session.staged_sheet_name}): "
                f"{len(created_supplier_ids)} supplier(s), {products_created} product(s) created, "
                f"{products_updated} updated, {len(created_offer_ids)} offer(s) created",
                {
                    "import_session_id": session_id,
                    "import_execution_id": execution.id,
                    "suppliers_created": len(created_supplier_ids),
                    "products_created": products_created,
                    "products_updated": products_updated,
                    "offers_created": len(created_offer_ids),
                    "skipped_row_count": 0,
                },
            )
            return execution

        except ImportExecutionError:
            db.session.rollback()
            raise
        except (BadRequest, Conflict, NotFound) as exc:
            description = getattr(exc, "description", None) or str(exc)
            self._fail_transaction(f"Import failed and was rolled back: {description}")
        except Exception as exc:
            db.session.rollback()
            raise ImportExecutionError(
                "Import failed unexpectedly and all uncommitted changes were rolled back."
            ) from exc

    def rollback(self, execution_id: int):
        # Lock the execution before checking its state. Two concurrent rollback
        # requests now serialize and the second request sees ROLLED_BACK.
        execution = self._lock_execution(execution_id)
        if execution.status == EXECUTION_STATUS_ROLLED_BACK:
            raise ImportExecutionError("This execution has already been rolled back.")

        for entry in execution.price_history or []:
            product = self.product_repo.get_by_id(entry["product_id"])
            if product is None:
                raise ImportExecutionError(
                    f"Cannot roll back: product #{entry['product_id']} no longer exists."
                )
            expected = entry.get("new_price")
            if expected is not None and float(product.current_price) != float(expected):
                raise Conflict(
                    f"Cannot roll back product #{product.id}: its price changed after this import."
                )

        try:
            for offer_id in execution.created_offer_ids or []:
                offer = self.offer_repo.get_by_id(offer_id)
                if offer is not None:
                    self.offer_repo.delete(offer)

            for entry in execution.price_history or []:
                if entry.get("old_price") is not None:
                    self.catalog_service.update_product(
                        entry["product_id"],
                        {"current_price": entry["old_price"]},
                    )

            for product_id in execution.created_product_ids or []:
                product = self.product_repo.get_by_id(product_id)
                if product is not None:
                    self.catalog_service.delete_product(product_id)

            for supplier_id in execution.created_supplier_ids or []:
                supplier = self.supplier_repo.get_by_id(supplier_id)
                if supplier is None:
                    continue
                if not self.product_repo.get_by_supplier(supplier_id) and not supplier.offered_products:
                    self.supplier_repo.delete(supplier)

            execution.status = EXECUTION_STATUS_ROLLED_BACK
            execution.rolled_back_by = self.user_id
            execution.rolled_back_at = datetime.now(timezone.utc)

            AuditService.log_event(
                self.tenant_id,
                self.user_id,
                "import.rolled_back",
                f"Rolled back import execution #{execution.id}",
                {
                    "import_execution_id": execution.id,
                    "import_session_id": execution.import_session_id,
                },
            )
            return execution
        except (BadRequest, Conflict, NotFound) as exc:
            db.session.rollback()
            description = getattr(exc, "description", None) or str(exc)
            raise ImportExecutionError(
                f"Rollback failed and was rolled back safely: {description}"
            ) from exc
        except Exception as exc:
            db.session.rollback()
            raise ImportExecutionError(
                "Rollback failed unexpectedly; no rollback changes were committed."
            ) from exc
