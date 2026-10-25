"""Supplier detection enrichment for import analysis.

Do not infer a whole-column supplier from its most common sample value:
mixed supplier values must be surfaced for manual review.
"""
def install_supplier_detection_patch():
    from app.services.import_analysis_service import WorkbookAnalyzer
    if getattr(WorkbookAnalyzer, "_supplier_detection_values_patch", False):
        return
    original = WorkbookAnalyzer._detect_suppliers

    def _detect_suppliers(self, columns):
        found = original(self, columns)
        for col in columns:
            if col.get("detected_type") != "SUPPLIER":
                continue
            idx = col.get("index")
            samples = [str(v).strip() for v in col.get("sample_values", []) if str(v).strip()]
            if not samples:
                continue

            unique = {}
            for value in samples:
                unique.setdefault(value.casefold(), value)
            values = list(unique.values())
            existing = next((item for item in found if item.get("column_index") == idx and item.get("source") in ("header", "column_values")), None)

            if len(values) != 1:
                if existing is None:
                    existing = {"column_index": idx, "header": col.get("header")}
                    found.append(existing)
                existing.update({
                    "source": "column_values",
                    "detected_supplier_name": None,
                    "matched_supplier_id": None,
                    "matched_supplier_name": None,
                    "ambiguous": True,
                    "candidate_supplier_names": values[:10],
                })
                continue

            value = values[0]
            match = self.known_supplier_names.get(value.casefold())
            if existing is None:
                existing = {"column_index": idx, "header": col.get("header")}
                found.append(existing)
            existing.update({
                "source": "column_values",
                "detected_supplier_name": value,
                "matched_supplier_id": match[0] if match else None,
                "matched_supplier_name": match[1] if match else value,
                "ambiguous": False,
                "candidate_supplier_names": [value],
            })
        return found

    WorkbookAnalyzer._detect_suppliers = _detect_suppliers
    WorkbookAnalyzer._supplier_detection_values_patch = True
