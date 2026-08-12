"""Import column mapping workspace, review, approval, and reusable templates."""
import re
from collections import Counter
from datetime import datetime, timezone

from werkzeug.exceptions import BadRequest, Conflict

from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_analysis_repository import ImportAnalysisRepository
from app.repositories.import_mapping_repository import (
    ImportMappingRepository,
    ImportMappingColumnRepository,
    ImportMappingTemplateRepository,
)
from app.repositories.supplier_repository import SupplierRepository
from app.models.import_mapping import (
    VALID_TARGETS,
    VALID_PRICE_TYPES,
    MAPPING_STATUS_APPROVED,
    TARGET_PRODUCT_NAME,
    TARGET_PRODUCT_CODE,
    TARGET_BARCODE,
    TARGET_CATEGORY,
    TARGET_UNIT,
    TARGET_SUPPLIER_NAME,
    TARGET_SUPPLIER_OFFER,
    TARGET_PRICE,
    TARGET_PRICE_BEFORE_VAT,
    TARGET_PRICE_AFTER_VAT,
    TARGET_DISCOUNT_PRICE,
    TARGET_IGNORE,
    PRICE_TYPE_REGULAR,
    PRICE_TYPE_BEFORE_VAT,
    PRICE_TYPE_AFTER_VAT,
    PRICE_TYPE_DISCOUNT,
)
from app.models.user import ROLE_ADMIN
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService

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
    "VAT": TARGET_PRICE_BEFORE_VAT,
    "DISCOUNT": TARGET_DISCOUNT_PRICE,
    "QUANTITY": TARGET_IGNORE,
    "NOTES": TARGET_IGNORE,
    "CODE": TARGET_IGNORE,
    "UNKNOWN": TARGET_IGNORE,
}
_ANALYSIS_TYPE_TO_PRICE_TYPE = {
    "PRICE": PRICE_TYPE_REGULAR,
    "PRICE_BEFORE_VAT": PRICE_TYPE_BEFORE_VAT,
    "PRICE_AFTER_VAT": PRICE_TYPE_AFTER_VAT,
    "VAT": PRICE_TYPE_BEFORE_VAT,
    "DISCOUNT": PRICE_TYPE_DISCOUNT,
}
_PRICE_LIKE_ANALYSIS_TYPES = set(_ANALYSIS_TYPE_TO_PRICE_TYPE)


class ImportMappingError(Exception):
    pass


def _normalize_filename(filename: str) -> str:
    return re.sub(r"^\d+_", "", filename or "").strip().lower()


def _normalize_supplier_value(value) -> str:
    """Normalize supplier cell values conservatively for exact catalog matching."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


def _is_positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _template_key(column_index: int, header: str) -> str:
    """Return a stable key that remains unique when a sheet repeats a header."""
    return f"{column_index}:{header}"


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
        self.user_repo = UserRepository(tenant_id)

    def get_or_create_mapping(self, session_id: int):
        if not _is_positive_int(session_id):
            raise BadRequest("Invalid import session id")

        session = self.session_repo.get_by_id_or_404(session_id)
        if not session.staged_sheet_name:
            raise ImportMappingError(
                "This session has no staged sheet to map yet (upload may have failed)."
            )

        existing = self.mapping_repo.get_by_session_and_sheet(
            session_id, session.staged_sheet_name
        )
        if existing:
            known_suppliers = {
                _normalize_supplier_value(s.name): (s.id, s.name)
                for s in self.supplier_repo.get_active()
            }
            self._auto_link_supplier_columns(existing, session, known_suppliers)
            return existing, self._find_matching_templates(session)

        analysis_rows = self.analysis_repo.get_by_session(session_id)
        analysis = next(
            (a for a in analysis_rows if a.sheet_name == session.staged_sheet_name),
            None,
        )
        mapping = self.mapping_repo.model(
            tenant_id=self.tenant_id,
            import_session_id=session_id,
            import_analysis_id=analysis.id if analysis else None,
            sheet_name=session.staged_sheet_name,
            created_by=self.user_id,
        )
        self.mapping_repo.add(mapping)

        known_suppliers = {
            _normalize_supplier_value(s.name): (s.id, s.name)
            for s in self.supplier_repo.get_active()
        }
        columns_data = analysis.columns if analysis else self._fallback_columns(session)
        self.column_repo.bulk_add(
            [
                self._build_suggested_column(mapping.id, col, known_suppliers, session)
                for col in columns_data
            ]
        )

        AuditService.log_event(
            self.tenant_id,
            self.user_id,
            "import.mapping_created",
            f"Created mapping for {session.filename} ({session.staged_sheet_name})",
            {"import_session_id": session_id, "import_mapping_id": mapping.id},
        )
        return mapping, self._find_matching_templates(session)

    @staticmethod
    def _fallback_columns(session):
        return [
            {
                "index": i,
                "header": h,
                "detected_type": "UNKNOWN",
                "confidence": "none",
                "group_label": None,
            }
            for i, h in enumerate(session.column_headers or [])
        ]

    def _supplier_match_from_rows(self, session, column_index: int, known_suppliers: dict):
        """Return a supplier only when the supplier column contains a strong, unambiguous match."""
        counts = Counter()
        total_non_empty = 0
        for row in getattr(session, "rows", []) or []:
            values = row.raw_values or []
            if column_index >= len(values):
                continue
            normalized = _normalize_supplier_value(values[column_index])
            if not normalized:
                continue
            total_non_empty += 1
            if normalized in known_suppliers:
                counts[normalized] += 1

        if not counts or total_non_empty < 1:
            return None

        winner, winner_count = counts.most_common(1)[0]
        share = winner_count / total_non_empty
        if winner_count < 2 or share < 0.80:
            return None

        supplier_id, supplier_name = known_suppliers[winner]
        return supplier_id, supplier_name, share

    def _auto_link_supplier_columns(self, mapping, session, known_suppliers):
        """Repair/enrich SUPPLIER columns from the actual staged cell values."""
        columns = self.column_repo.get_by_mapping(mapping.id)
        for col in columns:
            if col.final_target != TARGET_SUPPLIER_NAME and col.suggested_target != TARGET_SUPPLIER_NAME:
                continue
            if col.final_supplier_id is not None:
                continue
            match = self._supplier_match_from_rows(session, col.column_index, known_suppliers)
            if not match:
                continue
            supplier_id, supplier_name, share = match
            col.suggested_supplier_id = supplier_id
            col.suggested_supplier_name = supplier_name
            col.final_supplier_id = supplier_id
            col.final_supplier_name = supplier_name
            AuditService.log_event(
                self.tenant_id,
                self.user_id,
                "import.mapping_supplier_auto_linked",
                f'Auto-linked supplier "{supplier_name}" from import column "{col.column_header}"',
                {
                    "import_mapping_id": mapping.id,
                    "column_index": col.column_index,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "match_share": round(share, 4),
                },
            )
        return True

    def _build_suggested_column(self, mapping_id: int, col: dict, known_suppliers: dict, session=None):
        header = str(col.get("header") or "").strip()
        if not header:
            raise BadRequest("Import mapping contains a column with an empty header")

        detected_type = col.get("detected_type", "UNKNOWN")
        group_label = col.get("group_label")
        supplier_id = None
        supplier_name = None
        price_type = None

        if group_label and detected_type in _PRICE_LIKE_ANALYSIS_TYPES:
            target = TARGET_SUPPLIER_OFFER
            price_type = _ANALYSIS_TYPE_TO_PRICE_TYPE[detected_type]
            supplier_name = str(group_label).strip()
            match = known_suppliers.get(_normalize_supplier_value(supplier_name))
            if match:
                supplier_id, supplier_name = match
        elif detected_type == "SUPPLIER":
            target = TARGET_SUPPLIER_NAME
            match = known_suppliers.get(_normalize_supplier_value(header))
            if match:
                supplier_id, supplier_name = match
            elif session is not None:
                row_match = self._supplier_match_from_rows(session, col["index"], known_suppliers)
                if row_match:
                    supplier_id, supplier_name, _ = row_match
        else:
            target = _ANALYSIS_TYPE_TO_TARGET.get(detected_type, TARGET_IGNORE)

        return self.column_repo.model(
            tenant_id=self.tenant_id,
            import_mapping_id=mapping_id,
            column_index=col["index"],
            column_header=header,
            suggested_target=target,
            suggested_confidence=col.get("confidence") or "none",
            suggested_supplier_id=supplier_id,
            suggested_supplier_name=supplier_name,
            suggested_price_type=price_type,
            final_target=target,
            final_supplier_id=supplier_id,
            final_supplier_name=supplier_name,
            final_price_type=price_type,
            user_reviewed=False,
        )

    def update_columns(self, mapping_id: int, decisions: list):
        if not _is_positive_int(mapping_id):
            raise BadRequest("Invalid mapping id")
        if not isinstance(decisions, list):
            raise BadRequest("decisions must be an array")
        if len(decisions) > 1000:
            raise BadRequest("Too many mapping decisions")

        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        if mapping.status == MAPPING_STATUS_APPROVED:
            raise Conflict(
                "Approved mappings cannot be edited. Create a new import mapping instead."
            )

        columns_by_index = {
            c.column_index: c for c in self.column_repo.get_by_mapping(mapping_id)
        }
        seen_indexes = set()
        validated = []

        for decision in decisions:
            if not isinstance(decision, dict):
                raise BadRequest("Each mapping decision must be an object")
            column_index = decision.get("column_index")
            if not isinstance(column_index, int) or isinstance(column_index, bool) or column_index < 0:
                raise BadRequest("column_index must be a non-negative integer")
            if column_index in seen_indexes:
                raise BadRequest(f"Duplicate decision for column {column_index}")
            seen_indexes.add(column_index)
            if column_index not in columns_by_index:
                raise BadRequest(f"No column at index {column_index} in this mapping")

            target = decision.get("target")
            if target is not None and target not in VALID_TARGETS:
                raise BadRequest(f"Invalid target: {target}")
            price_type = decision.get("price_type")
            if price_type is not None and price_type not in VALID_PRICE_TYPES:
                raise BadRequest(f"Invalid price_type: {price_type}")
            if target == TARGET_SUPPLIER_OFFER:
                col = columns_by_index[column_index]
                if not (price_type or col.final_price_type):
                    raise BadRequest("price_type is required when target is SUPPLIER_OFFER")

            supplier_id = decision.get("supplier_id")
            if supplier_id is not None:
                if not _is_positive_int(supplier_id):
                    raise BadRequest("supplier_id must be a positive integer")
                self.supplier_repo.get_by_id_or_404(supplier_id)

            supplier_name = decision.get("supplier_name")
            if supplier_name is not None:
                if not isinstance(supplier_name, str) or not supplier_name.strip():
                    raise BadRequest("supplier_name must be a non-empty string")
                if len(supplier_name.strip()) > 255:
                    raise BadRequest("supplier_name is too long")

            validated.append((columns_by_index[column_index], decision))

        for col, decision in validated:
            if "target" in decision and decision["target"] is not None:
                col.final_target = decision["target"]
            if "supplier_id" in decision:
                col.final_supplier_id = decision["supplier_id"]
                if decision["supplier_id"] is not None:
                    supplier = self.supplier_repo.get_by_id_or_404(decision["supplier_id"])
                    col.final_supplier_name = supplier.name
                elif "supplier_name" in decision:
                    col.final_supplier_name = decision["supplier_name"].strip()
                    col.final_supplier_id = None
            elif "supplier_name" in decision:
                col.final_supplier_name = decision["supplier_name"].strip()
                col.final_supplier_id = None
            if "price_type" in decision and decision["price_type"] is not None:
                col.final_price_type = decision["price_type"]
            col.user_reviewed = True

        AuditService.log_event(
            self.tenant_id,
            self.user_id,
            "import.mapping_updated",
            f"Updated {len(decisions)} column mapping(s)",
            {"import_mapping_id": mapping_id, "column_count": len(decisions)},
        )
        return self.mapping_repo.get_by_id_or_404(mapping_id)

    def approve_mapping(self, mapping_id: int):
        if not _is_positive_int(mapping_id):
            raise BadRequest("Invalid mapping id")

        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        if mapping.status == MAPPING_STATUS_APPROVED:
            raise Conflict("This mapping is already approved")

        # Preserve maker-checker for managers/employees, but the tenant admin
        # is explicitly allowed to approve a mapping they created. The UI
        # exposes a single approval action and System Admin is the operational
        # owner of this internal system, so blocking the admin here produced a
        # misleading 409 even when the mapping itself was valid.
        creator = self.user_repo.get_by_id_or_404(mapping.created_by)
        approver = self.user_repo.get_by_id_or_404(self.user_id)
        if mapping.created_by == self.user_id and approver.role != ROLE_ADMIN:
            raise Conflict("The mapping creator cannot approve their own mapping")

        # The wizard explicitly presents the engine suggestions as the default
        # mapping and says they can be approved according to the suggestion.
        # Accept those suggestions automatically at approval time. We still
        # fail closed for an unresolved supplier because that could redirect
        # prices/offers to the wrong supplier.
        for col in mapping.columns:
            if col.user_reviewed or col.final_target == TARGET_IGNORE:
                continue
            if col.final_target != col.suggested_target:
                continue
            if col.final_target == TARGET_SUPPLIER_NAME and col.final_supplier_id is None:
                continue
            if col.final_target == TARGET_SUPPLIER_OFFER and col.final_supplier_id is None:
                continue
            if col.final_target in {
                TARGET_PRODUCT_NAME,
                TARGET_PRODUCT_CODE,
                TARGET_BARCODE,
                TARGET_CATEGORY,
                TARGET_UNIT,
                TARGET_PRICE,
                TARGET_PRICE_BEFORE_VAT,
                TARGET_PRICE_AFTER_VAT,
                TARGET_DISCOUNT_PRICE,
                TARGET_SUPPLIER_NAME,
                TARGET_SUPPLIER_OFFER,
            }:
                col.user_reviewed = True

        unreviewed = [
            c for c in mapping.columns
            if not c.user_reviewed and c.final_target != TARGET_IGNORE
        ]
        if unreviewed:
            raise Conflict(
                "Every non-ignored mapping column must be reviewed before approval: "
                + ", ".join(c.column_header for c in unreviewed[:10])
            )

        mapping.status = MAPPING_STATUS_APPROVED
        mapping.approved_by = self.user_id
        mapping.approved_at = datetime.now(timezone.utc)

        AuditService.log_event(
            self.tenant_id,
            self.user_id,
            "import.mapping_approved",
            f"Approved mapping for {mapping.sheet_name}",
            {
                "import_mapping_id": mapping_id,
                "reviewed_columns": len(mapping.columns),
                "approved_by": self.user_id,
                "created_by": mapping.created_by,
                "admin_self_approval": mapping.created_by == self.user_id,
            },
        )
        return mapping

    def get_mapping(self, mapping_id: int):
        return self.mapping_repo.get_by_id_or_404(mapping_id)

    def save_template(self, mapping_id: int, name: str, supplier_id: int = None):
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        if not isinstance(name, str) or not name.strip():
            raise BadRequest("Template name is required")
        name = name.strip()
        if len(name) > 255:
            raise BadRequest("Template name is too long")
        if supplier_id is not None:
            if not _is_positive_int(supplier_id):
                raise BadRequest("supplier_id must be a positive integer")
            self.supplier_repo.get_by_id_or_404(supplier_id)

        column_mapping = {
            _template_key(c.column_index, c.column_header): {
                "column_index": c.column_index,
                "column_header": c.column_header,
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
            self.tenant_id,
            self.user_id,
            "import.mapping_template_saved",
            f'Saved mapping template "{name}"',
            {"import_mapping_template_id": template.id, "import_mapping_id": mapping_id},
        )
        return template

    def list_templates(self):
        return self.template_repo.list_all()

    def _validate_template_scope(self, mapping, template):
        """Prevent a reusable template from silently switching suppliers."""
        session_supplier_id = mapping.session.supplier_id if mapping.session is not None else None
        template_supplier_id = template.supplier_id

        if session_supplier_id is not None and template_supplier_id is not None and session_supplier_id != template_supplier_id:
            raise Conflict("This template belongs to a different supplier and cannot be applied to this import.")

        embedded_supplier_ids = set()
        for entry in (template.column_mapping or {}).values():
            if not isinstance(entry, dict):
                continue
            supplier_id = entry.get("supplier_id")
            if supplier_id is not None:
                if not _is_positive_int(supplier_id):
                    raise Conflict("Template contains an invalid supplier_id")
                self.supplier_repo.get_by_id_or_404(supplier_id)
                embedded_supplier_ids.add(supplier_id)

        if template_supplier_id is not None:
            self.supplier_repo.get_by_id_or_404(template_supplier_id)
            if any(supplier_id != template_supplier_id for supplier_id in embedded_supplier_ids):
                raise Conflict("Template contains supplier mappings that do not match its supplier.")

        if session_supplier_id is not None:
            if any(supplier_id != session_supplier_id for supplier_id in embedded_supplier_ids):
                raise Conflict("Template contains supplier mappings for a different supplier than this import.")

    @staticmethod
    def _template_entry_for_column(template, col):
        mapping = template.column_mapping or {}
        exact = mapping.get(_template_key(col.column_index, col.column_header))
        if exact is not None:
            return exact
        legacy = mapping.get(col.column_header)
        if legacy is None:
            return None
        matching = [
            value for key, value in mapping.items()
            if isinstance(key, str) and key == col.column_header and isinstance(value, dict)
        ]
        return legacy if len(matching) == 1 else None

    def apply_template(self, mapping_id: int, template_id: int):
        mapping = self.mapping_repo.get_by_id_or_404(mapping_id)
        if mapping.status == MAPPING_STATUS_APPROVED:
            raise Conflict("Approved mappings cannot be changed")
        if not _is_positive_int(template_id):
            raise BadRequest("Invalid template id")
        template = self.template_repo.get_by_id_or_404(template_id)
        if not isinstance(template.column_mapping, dict):
            raise Conflict("The saved mapping template is invalid")

        self._validate_template_scope(mapping, template)

        applied_count = 0
        for col in mapping.columns:
            entry = self._template_entry_for_column(template, col)
            if entry is None:
                continue
            if not isinstance(entry, dict):
                raise Conflict(f"Invalid mapping entry for column {col.column_header}")
            target = entry.get("target", col.final_target)
            if target not in VALID_TARGETS:
                raise Conflict(f"Template contains invalid target for {col.column_header}")
            price_type = entry.get("price_type")
            if price_type is not None and price_type not in VALID_PRICE_TYPES:
                raise Conflict(f"Template contains invalid price_type for {col.column_header}")
            supplier_id = entry.get("supplier_id")
            if supplier_id is not None:
                if not _is_positive_int(supplier_id):
                    raise Conflict(f"Template contains invalid supplier_id for {col.column_header}")
                supplier = self.supplier_repo.get_by_id_or_404(supplier_id)
                supplier_name = supplier.name
            else:
                supplier_name = entry.get("supplier_name")

            if target == TARGET_SUPPLIER_OFFER and not price_type:
                raise Conflict(f"Template is missing price_type for {col.column_header}")

            col.final_target = target
            col.final_supplier_id = supplier_id
            col.final_supplier_name = supplier_name
            col.final_price_type = price_type
            col.user_reviewed = True
            applied_count += 1

        AuditService.log_event(
            self.tenant_id,
            self.user_id,
            "import.mapping_template_applied",
            f'Applied template "{template.name}" to {applied_count} column(s)',
            {
                "import_mapping_id": mapping_id,
                "import_mapping_template_id": template_id,
                "applied_count": applied_count,
            },
        )
        return mapping

    def _find_matching_templates(self, session):
        candidates = []
        if session.supplier_id:
            candidates.extend(self.template_repo.get_by_supplier(session.supplier_id))
        normalized = _normalize_filename(session.filename)
        for template in self.template_repo.list_all():
            if template in candidates:
                continue
            if template.source_filename and _normalize_filename(template.source_filename) == normalized:
                candidates.append(template)
        return candidates
