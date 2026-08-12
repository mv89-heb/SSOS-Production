"""Small production-safe fixes for import analysis and mapping behavior.

Kept separate from the large import engines so these targeted production fixes
can be deployed without rewriting the mature workbook parser/mapping service.
"""
from collections import Counter, OrderedDict
from difflib import SequenceMatcher


def _norm(value):
    return " ".join(str(value or "").strip().split()).casefold()


def _supplier_alias_match(value, known_suppliers):
    """Resolve a workbook supplier value to one catalog supplier."""
    value_norm = _norm(value)
    if not value_norm:
        return None

    exact = known_suppliers.get(value_norm)
    if exact:
        return exact

    value_tokens = set(value_norm.split())
    candidates = []
    for supplier_norm, supplier in known_suppliers.items():
        supplier_tokens = set(supplier_norm.split())
        if value_tokens and value_tokens.issubset(supplier_tokens) and any(len(t) >= 3 for t in value_tokens):
            score = 0.97 if value_tokens == supplier_tokens else 0.93
            candidates.append((score, supplier))
            continue
        if len(value_norm) >= 3 and value_norm in supplier_norm:
            candidates.append((0.90, supplier))
            continue
        similarity = SequenceMatcher(None, value_norm, supplier_norm).ratio()
        if similarity >= 0.90:
            candidates.append((similarity, supplier))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_supplier = candidates[0]
    if len(candidates) > 1 and best_score - candidates[1][0] < 0.04:
        return None
    return best_supplier


def _match_supplier_from_rows(session, column_index, known_suppliers):
    counts = Counter()
    total_non_empty = 0
    for row in getattr(session, "rows", []) or []:
        values = row.raw_values or []
        if column_index >= len(values):
            continue
        value = _norm(values[column_index])
        if not value:
            continue
        total_non_empty += 1
        match = _supplier_alias_match(value, known_suppliers)
        if match:
            supplier_id, supplier_name = match
            counts[supplier_id, supplier_name] += 1

    if not counts or total_non_empty < 1:
        return None
    (supplier_id, supplier_name), winner_count = counts.most_common(1)[0]
    share = winner_count / total_non_empty
    if winner_count < 2 or share < 0.80:
        return None
    if len(counts) > 1:
        _, second_count = counts.most_common(2)[1]
        if winner_count - second_count < max(1, int(total_non_empty * 0.10)):
            return None
    return supplier_id, supplier_name, share


def _analysis_supplier_for_column(analysis, column_index, known_suppliers):
    """Resolve a supplier from persisted ImportAnalysis.detected_suppliers."""
    if analysis is None:
        return None
    detected = getattr(analysis, "detected_suppliers", None) or []
    candidates = []
    for item in detected:
        if not isinstance(item, dict) or item.get("column_index") != column_index:
            continue
        supplier_id = item.get("matched_supplier_id")
        supplier_name = item.get("matched_supplier_name")
        if supplier_id and supplier_name:
            candidates.append((supplier_id, str(supplier_name)))

    unique = {(sid, name) for sid, name in candidates}
    if len(unique) == 1:
        return next(iter(unique))

    # Older analysis may have only the discovered display value in `header`.
    for item in detected:
        if not isinstance(item, dict) or item.get("column_index") != column_index:
            continue
        display = item.get("header")
        if not display:
            continue
        match = _supplier_alias_match(display, known_suppliers)
        if match:
            return match
    return None


def install_import_supplier_detection_fix():
    from app.services.import_analysis_service import WorkbookAnalyzer
    from app.services.import_mapping_service import ImportMappingService
    from app.extensions import db

    if getattr(WorkbookAnalyzer, "_supplier_values_fix_installed", False):
        return

    original_detect_suppliers = WorkbookAnalyzer._detect_suppliers

    def detect_suppliers(self, columns):
        found = original_detect_suppliers(self, columns)
        seen = {
            (
                item.get("column_index"),
                item.get("matched_supplier_id"),
                item.get("matched_supplier_name"),
            )
            for item in found
        }

        for col in columns:
            if col.get("detected_type") != "SUPPLIER":
                continue
            samples = col.get("sample_values") or []
            candidates = OrderedDict()
            for value in samples:
                display = " ".join(str(value or "").strip().split())
                key = _norm(display)
                if key and key not in candidates:
                    candidates[key] = display

            for key, display in candidates.items():
                match = _supplier_alias_match(key, self.known_supplier_names)
                if match:
                    supplier_id, real_name = match
                    marker = (col.get("index"), supplier_id, real_name)
                    if marker not in seen:
                        found.append({
                            "column_index": col.get("index"),
                            "header": display,
                            "source": "column_value",
                            "matched_supplier_id": supplier_id,
                            "matched_supplier_name": real_name,
                        })
                        seen.add(marker)

        cleaned = []
        for item in found:
            if (
                item.get("source") == "header"
                and item.get("header", "").strip().casefold()
                in {"שם ספק", "supplier", "supplier name", "ספק"}
            ):
                continue
            cleaned.append(item)
        return cleaned

    original_mapping_match = ImportMappingService._supplier_match_from_rows

    def mapping_supplier_match(self, session, column_index, known_suppliers):
        match = _match_supplier_from_rows(session, column_index, known_suppliers)
        if match:
            return match
        return original_mapping_match(self, session, column_index, known_suppliers)

    original_get_or_create = ImportMappingService.get_or_create_mapping

    def get_or_create_mapping_with_supplier_repair(self, session_id):
        mapping, templates = original_get_or_create(self, session_id)

        # The mapping service historically looked only at staged rows. In some
        # production requests those rows are not eagerly loaded, while the
        # analysis result already contains the exact supplier match. Repair the
        # persisted mapping directly from ImportAnalysis so the Select receives
        # final_supplier_id and never falls back to "בחר ספק..." unnecessarily.
        session = self.session_repo.get_by_id_or_404(session_id)
        analysis_rows = self.analysis_repo.get_by_session(session_id)
        analysis = next(
            (a for a in analysis_rows if a.sheet_name == session.staged_sheet_name),
            None,
        )
        known_suppliers = {
            _norm(s.name): (s.id, s.name)
            for s in self.supplier_repo.get_active()
        }

        changed = False
        for col in self.column_repo.get_by_mapping(mapping.id):
            if col.final_target != "SUPPLIER_NAME" and col.suggested_target != "SUPPLIER_NAME":
                continue
            if col.final_supplier_id is not None:
                continue
            match = _analysis_supplier_for_column(analysis, col.column_index, known_suppliers)
            if not match:
                continue
            supplier_id, supplier_name = match
            col.suggested_supplier_id = supplier_id
            col.suggested_supplier_name = supplier_name
            col.final_supplier_id = supplier_id
            col.final_supplier_name = supplier_name
            changed = True

        if changed:
            db.session.commit()
            mapping = self.mapping_repo.get_by_id_or_404(mapping.id)

        return mapping, templates

    WorkbookAnalyzer._detect_suppliers = detect_suppliers
    ImportMappingService._supplier_match_from_rows = mapping_supplier_match
    ImportMappingService.get_or_create_mapping = get_or_create_mapping_with_supplier_repair
    WorkbookAnalyzer._supplier_values_fix_installed = True
    ImportMappingService._supplier_alias_fix_installed = True
