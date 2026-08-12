"""Supplier detection enrichment for import analysis.

The workbook analyzer already identifies a SUPPLIER column and captures sample
values. This module enriches that result from the values themselves, so a
header such as "שם ספק" is never mistaken for the supplier's actual name.
"""
from collections import Counter


def install_supplier_detection_patch():
    from app.services.import_analysis_service import WorkbookAnalyzer

    if getattr(WorkbookAnalyzer, "_supplier_detection_values_patch", False):
        return

    original = WorkbookAnalyzer._detect_suppliers

    def _detect_suppliers(self, columns):
        found = original(self, columns)
        seen_columns = {item.get("column_index") for item in found}

        for col in columns:
            if col.get("detected_type") != "SUPPLIER":
                continue
            idx = col.get("index")
            samples = [str(v).strip() for v in col.get("sample_values", []) if str(v).strip()]
            if not samples:
                continue

            counts = Counter(samples)
            value = counts.most_common(1)[0][0]
            normalized = value.lower()
            match = self.known_supplier_names.get(normalized)

            # Replace the header-only result with the actual supplier value.
            for item in found:
                if item.get("column_index") == idx and item.get("source") == "header":
                    item.update({
                        "source": "column_values",
                        "detected_supplier_name": value,
                        "matched_supplier_id": match[0] if match else None,
                        "matched_supplier_name": match[1] if match else value,
                    })
                    break
            else:
                found.append({
                    "column_index": idx,
                    "header": col.get("header"),
                    "source": "column_values",
                    "detected_supplier_name": value,
                    "matched_supplier_id": match[0] if match else None,
                    "matched_supplier_name": match[1] if match else value,
                })

        return found

    WorkbookAnalyzer._detect_suppliers = _detect_suppliers
    WorkbookAnalyzer._supplier_detection_values_patch = True
