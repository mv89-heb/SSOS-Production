"""Production fix for TALL supplier columns in the Smart Import Wizard.

A TALL price list can contain many suppliers in one SUPPLIER_NAME column.
That column is a row-level mapping, so it must not be forced into one
session-level supplier_id. It is nevertheless a complete mapping decision
and therefore must be marked reviewed so Step 3 approval is not blocked.
"""
from collections import Counter


def _norm(value):
    return " ".join(str(value or "").strip().split()).casefold()


def install_tall_supplier_mapping_fix():
    from app.models.import_mapping import TARGET_SUPPLIER_NAME
    from app.services.import_mapping_service import ImportMappingService

    if getattr(ImportMappingService, "_tall_supplier_mapping_fix", False):
        return

    original_get_or_create = ImportMappingService.get_or_create_mapping
    original_approve = ImportMappingService.approve_mapping

    def _supplier_column_stats(service, session, column_index):
        rows = service.row_repo.get_all_by_session(session.id)
        known = {
            _norm(s.name): (s.id, s.name)
            for s in service.supplier_repo.get_active()
            if s.name
        }
        counts = Counter()
        total = 0
        for row in rows:
            values = row.raw_values or []
            if column_index >= len(values):
                continue
            value = _norm(values[column_index])
            if not value:
                continue
            total += 1
            match = known.get(value)
            if match:
                counts[match] += 1
                continue
            # Safe partial match for labels such as "אריאל" ->
            # "אריאל שיווק בשר". Ambiguous matches are ignored.
            candidates = []
            for normalized_name, supplier in known.items():
                if value in normalized_name or normalized_name in value:
                    candidates.append(supplier)
            unique = {(sid, name) for sid, name in candidates}
            if len(unique) == 1:
                counts[next(iter(unique))] += 1

        return counts, total

    def get_or_create_mapping(service, session_id):
        mapping, templates = original_get_or_create(service, session_id)
        session = service.session_repo.get_by_id_or_404(session_id)

        for col in mapping.columns:
            if col.final_target != TARGET_SUPPLIER_NAME and col.suggested_target != TARGET_SUPPLIER_NAME:
                continue

            # Existing explicit supplier selection is authoritative.
            if col.final_supplier_id is not None:
                col.user_reviewed = True
                if col.final_supplier_name is None:
                    supplier = service.supplier_repo.get_by_id_or_404(col.final_supplier_id)
                    col.final_supplier_name = supplier.name
                if session.supplier_id is None:
                    session.supplier_id = col.final_supplier_id
                continue

            counts, total = _supplier_column_stats(service, session, col.column_index)
            if not total:
                continue

            # One supplier across the whole column: this is safe to promote
            # to the session-level supplier and display by its canonical name.
            if len(counts) == 1:
                (supplier_id, supplier_name), count = counts.most_common(1)[0]
                if count / total >= 0.80:
                    col.suggested_supplier_id = supplier_id
                    col.suggested_supplier_name = supplier_name
                    col.final_supplier_id = supplier_id
                    col.final_supplier_name = supplier_name
                    col.user_reviewed = True
                    if session.supplier_id is None:
                        session.supplier_id = supplier_id
                    continue

            # Multiple suppliers in one TALL column: the mapping is complete
            # even though there is no single final_supplier_id. The validation
            # engine resolves the supplier per row. This is the critical fix
            # for files like "מוצר | ספק | מחיר".
            if counts:
                col.user_reviewed = True
                col.final_supplier_id = None
                col.final_supplier_name = None

        return mapping, templates

    def approve_mapping(service, mapping_id):
        mapping = service.mapping_repo.get_by_id_or_404(mapping_id)
        # Repair legacy mappings created before the TALL fix. Do this before
        # the original fail-closed approval validation.
        if mapping.status != "APPROVED":
            session = mapping.session
            if session is not None:
                for col in mapping.columns:
                    if col.final_target == TARGET_SUPPLIER_NAME or col.suggested_target == TARGET_SUPPLIER_NAME:
                        if col.final_supplier_id is None:
                            counts, total = _supplier_column_stats(service, session, col.column_index)
                            if counts:
                                col.user_reviewed = True
        return original_approve(service, mapping_id)

    ImportMappingService.get_or_create_mapping = get_or_create_mapping
    ImportMappingService.approve_mapping = approve_mapping
    ImportMappingService._tall_supplier_mapping_fix = True
