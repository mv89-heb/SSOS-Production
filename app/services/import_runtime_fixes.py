"""Small production-safe fixes for import analysis behavior.

Kept separate from the large analysis engine so this change can be deployed
without rewriting the mature workbook parser. The patch is installed from
wsgi.py before the first request and only changes supplier detection when a
real supplier column contains supplier names as row values.
"""
from collections import OrderedDict


def _norm(value):
    return " ".join(str(value or "").strip().split()).casefold()


def install_import_supplier_detection_fix():
    from app.services.import_analysis_service import WorkbookAnalyzer

    if getattr(WorkbookAnalyzer, "_supplier_values_fix_installed", False):
        return

    original = WorkbookAnalyzer._detect_suppliers

    def detect_suppliers(self, columns):
        # Preserve the original behavior for wide/merged supplier layouts.
        found = original(self, columns)
        seen = {
            (
                item.get("column_index"),
                item.get("matched_supplier_id"),
                item.get("matched_supplier_name"),
            )
            for item in found
        }

        # A normal tall import has a column such as "שם ספק" whose header
        # says SUPPLIER, while the actual supplier is in its row values.
        # Use sampled values from the already-analyzed column and resolve
        # them against the tenant's known supplier dictionary.
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
                match = self.known_supplier_names.get(key)
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
                elif not found:
                    # Do not pretend that "שם ספק" is the supplier. If the
                    # tenant has no matching supplier yet, expose the actual
                    # value so the UI can request supplier resolution.
                    found.append({
                        "column_index": col.get("index"),
                        "header": display,
                        "source": "column_value_unmatched",
                        "matched_supplier_id": None,
                        "matched_supplier_name": None,
                    })

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

    WorkbookAnalyzer._detect_suppliers = detect_suppliers
    WorkbookAnalyzer._supplier_values_fix_installed = True
