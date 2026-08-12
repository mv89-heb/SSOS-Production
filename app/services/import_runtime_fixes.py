"""Small production-safe fixes for import analysis and mapping behavior.

Kept separate from the large import engines so these targeted production fixes
can be deployed without rewriting the mature workbook parser/mapping service.
"""
from collections import Counter, OrderedDict
from difflib import SequenceMatcher


def _norm(value):
    return " ".join(str(value or "").strip().split()).casefold()


def _supplier_alias_match(value, known_suppliers):
    """Resolve a workbook supplier value to one catalog supplier.

    Supplier workbooks frequently use a short trading name (for example
    "אריאל") while the catalog stores the legal/expanded name (for example
    "אריאל שיווק בשר"). Exact matching alone therefore leaves the UI at
    "בחר ספק..." even when the supplier is obvious.

    We only accept deterministic matches: exact name, a complete token subset
    with a meaningful token, or a very strong string similarity. Ambiguous
    candidates are rejected instead of guessing.
    """
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
        shared = value_tokens & supplier_tokens

        # "אריאל" -> "אריאל שיווק בשר" is a safe alias when the supplied
        # value is a complete catalog token and is not just a 1-2 character
        # fragment.
        if value_tokens and value_tokens.issubset(supplier_tokens) and any(len(t) >= 3 for t in value_tokens):
            score = 0.97 if value_tokens == supplier_tokens else 0.93
            candidates.append((score, supplier))
            continue

        # Also support a short supplied value embedded in the canonical name,
        # but require at least three characters to avoid dangerous fragments.
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
    """Find the dominant supplier represented by a tall import column."""
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

    # Fail closed if two suppliers are represented with comparable evidence.
    if len(counts) > 1:
        _, second_count = counts.most_common(2)[1]
        if winner_count - second_count < max(1, int(total_non_empty * 0.10)):
            return None

    return supplier_id, supplier_name, share


def install_import_supplier_detection_fix():
    from app.services.import_analysis_service import WorkbookAnalyzer
    from app.services.import_mapping_service import ImportMappingService

    if getattr(WorkbookAnalyzer, "_supplier_values_fix_installed", False):
        return

    original_detect_suppliers = WorkbookAnalyzer._detect_suppliers

    def detect_suppliers(self, columns):
        # Preserve the original behavior for wide/merged supplier layouts.
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

        # Remove the old false-positive where the literal supplier-column
        # header was reported as the supplier.
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
        # The new alias-aware matcher handles short supplier names. Keep the
        # original implementation as a fallback so existing exact behavior is
        # preserved for unusual data structures.
        match = _match_supplier_from_rows(session, column_index, known_suppliers)
        if match:
            return match
        return original_mapping_match(self, session, column_index, known_suppliers)

    WorkbookAnalyzer._detect_suppliers = detect_suppliers
    ImportMappingService._supplier_match_from_rows = mapping_supplier_match
    WorkbookAnalyzer._supplier_values_fix_installed = True
    ImportMappingService._supplier_alias_fix_installed = True
