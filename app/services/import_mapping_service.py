"""
Phase 3.2B — Mapping Engine.

Converts ImportAnalysis's per-column type guesses into a structured,
human-reviewable mapping: which target field each column represents, which
supplier a WIDE-format price column belongs to, and what price "flavor"
it is. A person reviews, confirms, or overrides every column via the API;
none of this writes to products/suppliers/supplier_product_offers —
turning an approved mapping into catalog rows is Phase 3.2D (Import
Execution Engine), deliberately not this one.
"""
import re
from werkzeug.exceptions import BadRequest, NotFound

from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_analysis_repository import ImportAnalysisRepository
from app.repositories.import_mapping_repository import (
    ImportMappingRepository, ImportMappingColumnRepository, ImportMappingTemplateRepository,
)
from app.repositories.supplier_repository import SupplierRepository
from app.models.import_mapping import (
    VALID_TARGETS, VALID_PRICE_TYPES, MAPPING_STATUS_APPROVED,
    TARGET_PRODUCT_NAME, TARGET_PRODUCT_CODE, TARGET_BARCODE, TARGET_CATEGORY, TARGET_UNIT,
    TARGET_SUPPLIER_NAME, TARGET_SUPPLIER_OFFER, TARGET_PRICE, TARGET_PRICE_BEFORE_VAT,
    TARGET_PRICE_AFTER_VAT, TARGET_DISCOUNT_PRICE, TARGET_IGNORE,
    PRICE_TYPE_REGULAR, PRICE_TYPE_BEFORE_VAT, PRICE_TYPE_AFTER_VAT, PRICE_TYPE_DISCOUNT,
)
from app.services.audit_service import AuditService

# ImportAnalysis column detected_type -> suggested mapping target, for
# columns that are NOT supplier-attributed (i.e. no group_label, or a
# group_label that doesn't look like a distinct supplier — the plain TALL
# case, or a column that's simply not price-related at all).
_ANALYSIS_TYPE_TO_TARGET = {
    "PRODUCT_NAME": TARGET_PRODUCT_NAME,
    "PRODUCT_CODE": TARGET_PRODUCT_CODE,
    "BARCODE": TARGET_BARCODE,
    "CATEGORY": TARGET_CATEGORY,
    "UNIT": TARGET_UNIT,
    "SUPPLIER": TARGET_SUPPLIER_NAME,
    "PRICE": TARGET_PRICE,
    "PRICE_BEFORE_VAT": TARGET_PRICE_BEFORE_VAT,
    "PRICE_AFTER_VAT": TARGET_PRICE_AFTER_VAT,
    "VAT": TARGET_PRICE_BEFORE_VAT,  # ambiguous generic VAT mention — before_vat is the more common convention
    "DISCOUNT": TARGET_DISCOUNT_PRICE,
    "QUANTITY": TARGET_IGNORE,
    "NOTES": TARGET_IGNORE,
    "CODE": TARGET_IGNORE,
    "UNKNOWN": TARGET_IGNORE,
}

# Price-like analysis types -> price_type, used when a column IS
# supplier-attributed (has a group_label) and therefore suggested as
# SUPPLIER_OFFER instead of a plain pricing field.
_ANALYSIS_TYPE_TO_PRICE_TYPE = {
    "PRICE": PRICE_TYPE_REGULAR,
    "PRICE_BEFORE_VAT": PRICE_TYPE_BEFORE_VAT,
    "PRICE_AFTER_VAT": PRICE_TYPE_AFTER_VAT,
    "VAT": PRICE_TYPE_BEFORE_VAT,
    "DISCOUNT": PRICE_TYPE_DISCOUNT,
}
_PRICE_LIKE_ANALYSIS_TYPES = set(_ANALYSIS_TYPE_TO_PRICE_TYPE)


class ImportMappingError(Exception):
    """Raised when a mapping can't be built or a decision can't be applied."""


def _normalize_filename(filename: str) -> str:
    """Strips a leading upload-timestamp prefix (e.g. "1784449037643_") so
    the same source file re-uploaded later still matches for template
    suggestions, even though the stored filename includes a fresh prefix
    each time."""
    return re.sub(r"^\d+_", "", filename or "").strip().lower()


class ImportMappingService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_repo = ImportSessionRepository(tenant_id)
        self.analysis_repo = ImportAnalysisRepository(tenant_id)
        self.mapping_repo = ImportMappingRepository(tenant_id)
        self.column_repo = ImportMappingColumnRepository(tenant_id)
        self.template_repo = ImportMappingTemplateRepository(tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id)

    # ------------------------------------------------------------------
    # Build / fetch the mapping workspace
    # ------------------------------------------------------------------
    def get_or_create_mapping(self, session_id: int):
        """Returns (mapping, matching_templates). Creates the mapping (with
        fresh suggestions from ImportAnalysis) on first call; subsequent
        calls return the same mapping with whatever decisions have been
        saved so far — this never regenerates suggestions over a person's
        existing work."""
        session = self.session_repo.get_by_id_or_404(session_id)
        if not session.staged_sheet_name:
            raise ImportMappingError(
                "This session has no staged sheet to map yet (upload may have failed)."
            )

        existing = self.mapping_repo.get_by_session_and_sheet(session_id, session.staged_sheet_name)
        if existing:
            return existing, self._find_matching_templates(session)

        analysis_rows = self.analysis_repo.get_by_session(session_id)
        analysis = next((a for a in analysis_rows if a.sheet_name == session.staged_sheet_name), None)

        mapping = self.mapping_repo.model(
            tenant_id=self.tenant_id,
            import_session_id=session_id,
            import_analysis_id=analysis.id if analysis else None,
            sheet_name=session.staged_sheet_name,
            created_by=self.user_id,
        )
        self.mapping_repo.add(mapping)  # flush -> mapping.id populated

        known_suppliers = {
            s.name.strip().lower(): (s.id, s.name) for s in self.supplier_repo.get_active()
        }
        columns_data = analysis.columns if analysis else self._fallback_columns(session)
        column_rows = [
            self._build_suggested_column(mapping.id, col, known_suppliers)
            for col in columns_data
        ]
        self.column_repo.bulk_add(column_rows)

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.mapping_created",
            f"Created mapping for {session.filename} ({session.staged_sheet_name})",
            {"import_session_id": session_id, "import_mapping_id": mapping.id},
        )
        return mapping, self._find_matching_templates(session)

    @staticmethod
    def _fallback_columns(session):
        """If analysis was never run for this session, still let mapping
        proceed using just the (unclassified) staged column headers —
        every column suggested as UNKNOWN/IGNORE, fully editable."""
        return [
            {"index": i, "header": h, "detected_type": "UNKNOWN", "confidence": "none", "group_label": None}
            for i, h in enumerate(session.column_headers or [])
        ]

    def _build_suggested_column(self, mapping_id: int, col: dict, known_suppliers: dict):
        header = col["header"]
        detected_type = col["detected_type"]
        confidence = col["confidence"]
        group_label = col.get("group_label")

        supplier_id = None
        supplier_name = None
        price_type = None

        if group_label and detected_type in _PRICE_LIKE_ANALYSIS_TYPES:
            # WIDE format: this column IS a specific supplier's price.
            target = TARGET_SUPPLIER_OFFER
            price_type = _ANALYSIS_TYPE_TO_PRICE_TYPE[detected_type]
            supplier_name = group_label
            match = known_suppliers.get(group_label.strip().lower())
            if match:
                supplier_id = match[0]
                supplier_name = match[1]
        elif detected_type == "SUPPLIER":
            target = TARGET_SUPPLIER_NAME
            match = known_suppliers.get(header.strip().lower())
            if match:
                supplier_id, supplier_name = match
        else:
            target = _ANALYSIS_TYPE_TO_TARGET.get(detected_type, TARGET_IGNORE)

        return self.column_repo.model(
            tenant_id=self.tenant_id,
            import_mapping_id=mapping_id,
            column_index=col["index"],
            column_header=header,
            suggested_target=target,
            suggested_confidence=confidence,
            suggested_supplier_id=supplier_id,
            suggested_supplier_name=supplier_name,
            suggested_price_type=price_type,
            final_target=target,
            final_supplier_id=supplier_id,
            final_supplier_name=supplier_name,
            final_price_type=price_type,
            user_reviewed=False,
        )

    # ------------------------------------------------------------------
    # Review / override
    # ------------------------------------------------------------------
    def update_columns(self, mapping_id: int, decisions: list):
        """Applies a batch of per-column overrides. Each decision is
        {column_index, target, supplier_id?, supplier_name?, price_type?}.
        Validates every value before applying any of them, so a bad
        request can't leave the mapping half-updated."""
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        columns_by_index = {c.column_index: c for c in self.column_repo.get_by_mapping(mapping_id)}

        for decision in decisions:
            if "column_index" not in decision:
                raise BadRequest("Each decision must include column_index.")
            if decision["column_index"] not in columns_by_index:
                raise BadRequest(f"No column at index {decision['column_index']} in this mapping.")
            target = decision.get("target")
            if target is not None and target not in VALID_TARGETS:
                raise BadRequest(f"Invalid target: {target}")
            price_type = decision.get("price_type")
            if price_type is not None and price_type not in VALID_PRICE_TYPES:
                raise BadRequest(f"Invalid price_type: {price_type}")
            if target == TARGET_SUPPLIER_OFFER:
                col = columns_by_index[decision["column_index"]]
                effective_price_type = decision.get("price_type") or col.final_price_type
                if not effective_price_type:
                    raise BadRequest("price_type is required when target is SUPPLIER_OFFER.")
            supplier_id = decision.get("supplier_id")
            if supplier_id is not None:
                self.supplier_repo.get_by_id_or_404(supplier_id)  # tenant ownership check

        for decision in decisions:
            col = columns_by_index[decision["column_index"]]
            if "target" in decision and decision["target"] is not None:
                col.final_target = decision["target"]
            if "supplier_id" in decision:
                col.final_supplier_id = decision["supplier_id"]
                if decision["supplier_id"] is not None:
                    supplier = self.supplier_repo.get_by_id_or_404(decision["supplier_id"])
                    col.final_supplier_name = supplier.name
                elif "supplier_name" in decision:
                    col.final_supplier_name = decision["supplier_name"]
            elif "supplier_name" in decision:
                # A manual/new supplier name given without an id must clear
                # any stale id left over from a previous suggestion/decision
                # — otherwise final_supplier_name and final_supplier_id end
                # up pointing at two different suppliers.
                col.final_supplier_name = decision["supplier_name"]
                col.final_supplier_id = None
            if "price_type" in decision and decision["price_type"] is not None:
                col.final_price_type = decision["price_type"]
            col.user_reviewed = True

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.mapping_updated",
            f"Updated {len(decisions)} column mapping(s)",
            {"import_mapping_id": mapping_id, "column_count": len(decisions)},
        )
        return self.mapping_repo.get_by_id_or_404(mapping_id)

    def approve_mapping(self, mapping_id: int):
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        mapping.status = MAPPING_STATUS_APPROVED
        mapping.approved_by = self.user_id
        from datetime import datetime, timezone
        mapping.approved_at = datetime.now(timezone.utc)

        unreviewed = [c for c in mapping.columns if not c.user_reviewed and c.final_target != TARGET_IGNORE]
        AuditService.log_event(
            self.tenant_id, self.user_id, "import.mapping_approved",
            f"Approved mapping for {mapping.sheet_name}",
            {
                "import_mapping_id": mapping_id,
                "unreviewed_non_ignored_columns": [c.column_header for c in unreviewed],
            },
        )
        return mapping

    def get_mapping(self, mapping_id: int):
        return self.mapping_repo.get_by_id_or_404(mapping_id)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    def save_template(self, mapping_id: int, name: str, supplier_id: int = None):
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        if supplier_id is not None:
            self.supplier_repo.get_by_id_or_404(supplier_id)

        column_mapping = {
            c.column_header: {
                "target": c.final_target,
                "supplier_id": c.final_supplier_id,
                "supplier_name": c.final_supplier_name,
                "price_type": c.final_price_type,
            }
            for c in mapping.columns
        }

        template = self.template_repo.model(
            tenant_id=self.tenant_id,
            supplier_id=supplier_id,
            name=name,
            source_filename=mapping.session.filename if mapping.session else None,
            column_mapping=column_mapping,
            created_by=self.user_id,
        )
        self.template_repo.add(template)

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.mapping_template_saved",
            f'Saved mapping template "{name}"',
            {"import_mapping_template_id": template.id, "import_mapping_id": mapping_id},
        )
        return template

    def list_templates(self):
        return self.template_repo.list_all()

    def apply_template(self, mapping_id: int, template_id: int):
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        template = self.template_repo.get_by_id_or_404(template_id)

        applied_count = 0
        for col in mapping.columns:
            entry = template.column_mapping.get(col.column_header)
            if not entry:
                continue
            col.final_target = entry.get("target", col.final_target)
            col.final_supplier_id = entry.get("supplier_id")
            col.final_supplier_name = entry.get("supplier_name")
            col.final_price_type = entry.get("price_type")
            col.user_reviewed = True
            applied_count += 1

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.mapping_template_applied",
            f'Applied template "{template.name}" to {applied_count} column(s)',
            {"import_mapping_id": mapping_id, "import_mapping_template_id": template_id},
        )
        return mapping

    def _find_matching_templates(self, session):
        """Suggestion only — never applied automatically. Matches by
        supplier_id (if this session is already tied to one) or by a
        normalized source filename (strips the upload-time uuid/timestamp
        prefix so the same file re-uploaded later still matches)."""
        candidates = []
        if session.supplier_id:
            candidates.extend(self.template_repo.get_by_supplier(session.supplier_id))

        normalized = _normalize_filename(session.filename)
        for t in self.template_repo.list_all():
            if t in candidates:
                continue
            if t.source_filename and _normalize_filename(t.source_filename) == normalized:
                candidates.append(t)

        return candidates
