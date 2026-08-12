"""Safe, price-only execution for existing catalog products.

This service intentionally differs from the general import execution engine:
it NEVER creates products, suppliers, or alternate offers. It only updates
existing products that validation matched, and records old/new prices so the
normal import rollback mechanism can restore them.
"""
from sqlalchemy import select
from werkzeug.exceptions import Conflict, NotFound

from app.extensions import db
from app.models.import_execution import (
    ImportExecution,
    EXECUTION_STATUS_COMMITTED,
)
from app.models.import_mapping import MAPPING_STATUS_APPROVED
from app.models.import_session import ImportSession
from app.models.import_validation import VALIDATION_STATUS_COMPLETED, ACTION_UPDATE
from app.repositories.import_execution_repository import ImportExecutionRepository
from app.repositories.import_mapping_repository import ImportMappingRepository
from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_validation_repository import (
    ImportValidationRepository,
    ImportPreviewRepository,
)
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.services.catalog_service import CatalogService


class BulkPriceUpdateError(Exception):
    """Raised when a price-only update cannot be completed safely."""


class BulkPriceUpdateService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_repo = ImportSessionRepository(tenant_id)
        self.mapping_repo = ImportMappingRepository(tenant_id)
        self.validation_repo = ImportValidationRepository(tenant_id)
        self.preview_repo = ImportPreviewRepository(tenant_id)
        self.execution_repo = ImportExecutionRepository(tenant_id)
        self.product_repo = ProductRepository(tenant_id)
        self.catalog_service = CatalogService(tenant_id, user_id)

    def _lock_session(self, session_id: int):
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

    def preview(self, session_id: int):
        """Return a safe summary of what a price-only commit will do."""
        self.session_repo.get_by_id_or_404(session_id)
        validation = self.validation_repo.get_latest_by_session(session_id)
        if not validation or validation.status != VALIDATION_STATUS_COMPLETED:
            raise BulkPriceUpdateError("Validation must complete successfully first.")

        rows = self.preview_repo.get_all_by_validation(validation.id)
        if not rows:
            raise BulkPriceUpdateError("Validation produced no rows.")

        errors = [r.row_number for r in rows if r.has_errors]
        if errors:
            raise BulkPriceUpdateError(
                "Price update is blocked because validation contains errors in row(s): "
                + ", ".join(str(n) for n in errors[:20])
            )

        matched = [r for r in rows if r.product_action == ACTION_UPDATE and r.matched_product_id]
        unmatched = [
            {"row_number": r.row_number, "product_name": r.product_name}
            for r in rows
            if r.product_action != ACTION_UPDATE or not r.matched_product_id
        ]

        seen = set()
        duplicate_matches = []
        for row in matched:
            if row.matched_product_id in seen:
                duplicate_matches.append(row.row_number)
            seen.add(row.matched_product_id)
        if duplicate_matches:
            raise BulkPriceUpdateError(
                "The same catalog product is matched by multiple rows: "
                + ", ".join(str(n) for n in duplicate_matches[:20])
            )

        return {
            "validation_id": validation.id,
            "rows_in_file": len(rows),
            "products_to_update": len(matched),
            "rows_skipped": len(unmatched),
            "skipped_rows": unmatched[:200],
            "price_changes": [
                {
                    "row_number": r.row_number,
                    "product_id": r.matched_product_id,
                    "product_name": r.product_name,
                    "old_price": float(r.old_price) if r.old_price is not None else None,
                    "new_price": float(r.price) if r.price is not None else None,
                }
                for r in matched
            ],
        }

    def commit(self, session_id: int):
        """Update only already-existing matched products; never create data."""
        session = self._lock_session(session_id)
        mapping = self.mapping_repo.get_by_session_and_sheet(
            session_id, session.staged_sheet_name
        )
        if not mapping or mapping.status != MAPPING_STATUS_APPROVED:
            raise BulkPriceUpdateError("The mapping must be approved before updating prices.")

        validation = self.validation_repo.get_latest_by_session(session_id)
        if not validation or validation.status != VALIDATION_STATUS_COMPLETED:
            raise BulkPriceUpdateError("Validation must complete successfully before updating prices.")

        previous = self.execution_repo.get_latest_by_session(session_id)
        if previous and previous.status == EXECUTION_STATUS_COMMITTED:
            raise BulkPriceUpdateError(
                "This session already has a committed execution. Roll it back before running it again."
            )

        rows = self.preview_repo.get_all_by_validation(validation.id)
        if not rows:
            raise BulkPriceUpdateError("Validation produced no rows.")

        invalid_rows = [r.row_number for r in rows if r.has_errors]
        if invalid_rows:
            raise BulkPriceUpdateError(
                "Price update blocked by validation errors in row(s): "
                + ", ".join(str(n) for n in invalid_rows[:20])
            )

        update_rows = [
            r for r in rows
            if r.product_action == ACTION_UPDATE and r.matched_product_id
        ]
        seen_products = set()
        for row in update_rows:
            if row.matched_product_id in seen_products:
                raise BulkPriceUpdateError(
                    f"Product #{row.matched_product_id} is matched more than once in the file."
                )
            seen_products.add(row.matched_product_id)
            if row.price is None:
                raise BulkPriceUpdateError(f"Row {row.row_number}: price is missing.")
            if row.old_price is None:
                raise BulkPriceUpdateError(
                    f"Row {row.row_number}: existing product has no current price; refusing to update it in price-only mode."
                )

        snapshot_products = len(self.product_repo.get_all_for_matching())
        price_history = []
        skipped_rows = [
            {"row_number": r.row_number, "reason": "product_not_matched_or_new_product"}
            for r in rows
            if r.product_action != ACTION_UPDATE or not r.matched_product_id
        ]

        try:
            for row in update_rows:
                product = self.product_repo.get_by_id(row.matched_product_id)
                if product is None:
                    raise BulkPriceUpdateError(
                        f"Row {row.row_number}: matched product #{row.matched_product_id} no longer exists."
                    )

                current_price = float(product.current_price)
                expected_old_price = float(row.old_price)
                if current_price != expected_old_price:
                    raise Conflict(
                        f"Row {row.row_number}: price changed since validation "
                        f"({expected_old_price} -> {current_price}). Re-validate before updating."
                    )

                new_price = float(row.price)
                if new_price < 0:
                    raise BulkPriceUpdateError(f"Row {row.row_number}: price cannot be negative.")

                if current_price == new_price:
                    continue

                self.catalog_service.update_product(
                    product.id,
                    {"current_price": new_price},
                )
                price_history.append(
                    {
                        "product_id": product.id,
                        "old_price": current_price,
                        "new_price": new_price,
                    }
                )

            execution = self.execution_repo.model(
                tenant_id=self.tenant_id,
                import_session_id=session_id,
                import_validation_id=validation.id,
                status=EXECUTION_STATUS_COMMITTED,
                snapshot_suppliers_before=0,
                snapshot_products_before=snapshot_products,
                snapshot_offers_before=0,
                suppliers_created=0,
                products_created=0,
                products_updated=len(price_history),
                offers_created=0,
                created_supplier_ids=[],
                created_product_ids=[],
                created_offer_ids=[],
                price_history=price_history,
                skipped_rows=skipped_rows,
                executed_by=self.user_id,
            )
            self.execution_repo.add(execution)

            AuditService.log_event(
                self.tenant_id,
                self.user_id,
                "catalog.bulk_prices_updated",
                f"Bulk price update from {session.filename}: {len(price_history)} product(s) updated",
                {
                    "import_session_id": session_id,
                    "import_execution_id": execution.id,
                    "products_updated": len(price_history),
                    "rows_skipped": len(skipped_rows),
                },
            )
            return execution
        except (BulkPriceUpdateError, Conflict):
            db.session.rollback()
            raise
        except Exception as exc:
            db.session.rollback()
            raise BulkPriceUpdateError(
                "Bulk price update failed unexpectedly; no changes were committed."
            ) from exc
