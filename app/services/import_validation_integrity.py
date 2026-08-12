"""Post-validation integrity repairs for supplier imports.

This module intentionally sits around the existing validation engine instead of
rewriting it. The production importer stores staged rows as ordered raw values,
so a lightweight O(n) grouping is safer than introducing pandas into the
runtime just for validation.
"""
from collections import defaultdict

from app.extensions import db
from app.models.import_mapping import TARGET_PRODUCT_NAME, TARGET_SUPPLIER_NAME
from app.models.import_validation import (
    ACTION_CREATE,
    ACTION_ERROR,
    ACTION_SKIP,
    ACTION_UPDATE,
    ImportIssue,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)

DEFAULT_IMPORT_UNIT = 'ק"ג'
DUPLICATE_ERROR_CODE = "CRITICAL_ERROR"
DUPLICATE_ERROR_MESSAGE = "שגיאת כפילות: המוצר מופיע מספר פעמים בקובץ. כל השורות המעורבות ידולגו"


def _norm(value):
    return " ".join(str(value or "").strip().casefold().split())


def _value_for(row, columns_by_index, target):
    values = row.raw_values or []
    for index, column in columns_by_index.items():
        if column.final_target != target or index >= len(values):
            continue
        value = str(values[index] or "").strip()
        if value:
            return value
    return None


def find_duplicate_row_numbers(rows, columns_by_index, session_supplier_name=None, resolved_supplier_by_row=None):
    """Return every row number participating in a duplicate product+supplier key."""
    groups = defaultdict(list)
    resolved_supplier_by_row = resolved_supplier_by_row or {}
    for row in rows:
        product_name = _norm(_value_for(row, columns_by_index, TARGET_PRODUCT_NAME))
        raw_supplier = _value_for(row, columns_by_index, TARGET_SUPPLIER_NAME) or session_supplier_name
        resolved_supplier = resolved_supplier_by_row.get(row.row_number)
        supplier_key = f"id:{resolved_supplier}" if resolved_supplier else _norm(raw_supplier)
        if product_name and supplier_key:
            groups[(product_name, supplier_key)].append(row.row_number)

    duplicate_rows = set()
    for row_numbers in groups.values():
        if len(row_numbers) > 1:
            duplicate_rows.update(row_numbers)
    return duplicate_rows


def _remove_replaced_issues(validation):
    """Remove the old soft warnings that are superseded by the integrity layer."""
    for issue in list(validation.issues or []):
        if issue.code == "missing_unit" or issue.code == "duplicate_in_file":
            db.session.delete(issue)


def apply_integrity_repairs(validation, session, mapping, rows):
    """Apply non-negotiable data-integrity rules after normal validation.

    1. Every preview row receives a safe default unit when the workbook has no
       usable mapped unit value.
    2. Every occurrence of the same product+supplier pair becomes a hard row
       error. No occurrence can reach ImportExecutionService.
    """
    columns_by_index = {column.column_index: column for column in mapping.columns}
    previews = list(validation.preview_rows or [])
    preview_by_row = {preview.row_number: preview for preview in previews}

    # Unit fallback is deliberately applied to every row, not only CREATE rows.
    # Existing products are not rewritten by execution on UPDATE, but their
    # preview remains complete and deterministic.
    for preview in previews:
        if not preview.unit:
            preview.unit = DEFAULT_IMPORT_UNIT

    resolved_supplier_by_row = {
        preview.row_number: preview.matched_supplier_id
        for preview in previews
        if preview.matched_supplier_id is not None
    }
    duplicate_row_numbers = find_duplicate_row_numbers(
        rows,
        columns_by_index,
        session_supplier_name=session.supplier.name if session.supplier else None,
        resolved_supplier_by_row=resolved_supplier_by_row,
    )

    _remove_replaced_issues(validation)

    duplicate_rows = [
        preview_by_row[row_number]
        for row_number in sorted(duplicate_row_numbers)
        if row_number in preview_by_row
    ]

    all_duplicate_numbers = sorted(duplicate_row_numbers)
    for preview in duplicate_rows:
        preview.product_action = ACTION_ERROR
        preview.has_errors = True
        issue = ImportIssue(
            tenant_id=validation.tenant_id,
            import_validation_id=validation.id,
            row_number=preview.row_number,
            field="product_name",
            severity=SEVERITY_ERROR,
            code=DUPLICATE_ERROR_CODE,
            message=f"{DUPLICATE_ERROR_MESSAGE} (שורות: {', '.join(map(str, all_duplicate_numbers))})",
        )
        db.session.add(issue)
        validation.issues.append(issue)

    # Recompute persisted summary from the repaired preview so Step 4/6 and
    # ImportExecutionService see exactly the same truth.
    validation.products_to_create = sum(
        p.product_action == ACTION_CREATE and not p.has_errors for p in previews
    )
    validation.products_to_update = sum(
        p.product_action == ACTION_UPDATE and not p.has_errors for p in previews
    )
    validation.products_to_skip = sum(
        p.product_action == ACTION_SKIP and not p.has_errors for p in previews
    )
    valid_previews = [p for p in previews if not p.has_errors]
    validation.offers_to_create = sum(
        1 for p in valid_previews for offer in (p.offers or []) if offer.get("action") == ACTION_CREATE
    )
    validation.offers_to_update = sum(
        1 for p in valid_previews for offer in (p.offers or []) if offer.get("action") == ACTION_UPDATE
    )

    supplier_names = {
        _norm(p.supplier_name)
        for p in valid_previews
        if p.supplier_action == ACTION_CREATE and p.supplier_name
    }
    validation.suppliers_to_create = len(supplier_names)

    # Missing-unit warnings were replaced by the safe default; duplicate
    # warnings were replaced by CRITICAL_ERROR rows.
    remaining_issues = [
        issue
        for issue in (validation.issues or [])
        if issue.code not in {"missing_unit", "duplicate_in_file"}
    ]
    validation.warning_count = sum(
        issue.severity == SEVERITY_WARNING for issue in remaining_issues
    )
    validation.error_count = sum(
        issue.severity == SEVERITY_ERROR for issue in remaining_issues
    )

    return duplicate_row_numbers


def install_import_validation_integrity_patch():
    """Patch the mature validation service once during Flask app startup."""
    from app.services.import_validation_service import ImportValidationService

    if getattr(ImportValidationService, "_integrity_patch_installed", False):
        return

    original_validate = ImportValidationService.validate

    def validate_with_integrity(self, session_id):
        validation = original_validate(self, session_id)
        session = self.session_repo.get_by_id_or_404(session_id)
        mapping = self.mapping_repo.get_by_session_and_sheet(session_id, session.staged_sheet_name)
        rows = self.row_repo.get_all_by_session(session_id)
        apply_integrity_repairs(validation, session, mapping, rows)
        db.session.flush()
        return validation

    ImportValidationService.validate = validate_with_integrity
    ImportValidationService._integrity_patch_installed = True
