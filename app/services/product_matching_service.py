from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from app.models.product import Product
from app.models.supplier import Supplier


class ProductMatchingService:
    """Match extracted document lines to the tenant catalog without mutating it."""

    STOP_WORDS = {
        "של", "עם", "ל", "ב", "מ", "ו", "ה", "את", "על", "או", "גרם", "קג",
        "קילו", "מיליליטר", "מ\"ל", "ליטר", "יח", "יחידה", "יחידות", "מארז", "אריזה",
        "the", "and", "of", "for", "with", "pack", "package", "unit", "units",
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self._products: list[Product] | None = None
        self._suppliers: list[Supplier] | None = None

    @classmethod
    def normalize(cls, value) -> str:
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value)).casefold()
        text = text.replace("\u05f3", "'").replace("\u05f4", '"')
        text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text)
        text = re.sub(r"[^\w\u0590-\u05ff]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def compact(cls, value) -> str:
        return re.sub(r"[^0-9a-z\u0590-\u05ff]+", "", cls.normalize(value))

    @classmethod
    def tokens(cls, value) -> set[str]:
        return {token for token in cls.normalize(value).split() if len(token) > 1 and token not in cls.STOP_WORDS}

    @classmethod
    def _text_score(cls, left, right) -> float:
        a, b = cls.normalize(left), cls.normalize(right)
        if not a or not b:
            return 0.0
        sequence = SequenceMatcher(None, a, b).ratio()
        at, bt = cls.tokens(a), cls.tokens(b)
        if at and bt:
            return max(sequence, len(at & bt) / max(len(at), len(bt)))
        return sequence

    @classmethod
    def _identity_score(cls, extracted, product) -> tuple[float, str | None]:
        barcode = cls.compact(extracted.get("barcode"))
        product_barcode = cls.compact(product.barcode)
        if barcode and product_barcode and barcode == product_barcode:
            return 1.0, "BARCODE"
        supplier_sku = cls.compact(extracted.get("supplier_sku"))
        product_supplier_sku = cls.compact(product.supplier_sku)
        product_sku = cls.compact(product.sku)
        if supplier_sku and product_supplier_sku and supplier_sku == product_supplier_sku:
            return 0.99, "SUPPLIER_SKU"
        if supplier_sku and product_sku and supplier_sku == product_sku:
            return 0.97, "SKU"
        return 0.0, None

    @classmethod
    def _candidate_score(cls, extracted, product, supplier_id: int | None = None) -> tuple[float, str]:
        identity, method = cls._identity_score(extracted, product)
        if identity:
            return identity, method
        description = extracted.get("description") or ""
        score = max(cls._text_score(description, product.name), cls._text_score(description, product.description) * 0.92)
        extracted_unit = cls.normalize(extracted.get("unit"))
        product_unit = cls.normalize(product.unit)
        if extracted_unit and product_unit and extracted_unit == product_unit:
            score = min(1.0, score + 0.03)
        package_quantity = extracted.get("package_quantity")
        if package_quantity is not None and product.units_per_carton is not None:
            try:
                if float(package_quantity) == float(product.units_per_carton):
                    score = min(1.0, score + 0.02)
            except (TypeError, ValueError):
                pass
        if supplier_id is not None and product.supplier_id == supplier_id:
            score = min(1.0, score + 0.05)
        return round(score, 4), "NAME_SIMILARITY"

    def _load_catalog(self):
        if self._products is None:
            self._products = list(Product.query.filter_by(tenant_id=self.tenant_id, active=True).all())
        if self._suppliers is None:
            self._suppliers = list(Supplier.query.filter_by(tenant_id=self.tenant_id, active=True).all())

    def match_supplier(self, supplier_data: dict | None):
        self._load_catalog()
        supplier_data = supplier_data or {}
        customer_number = self.compact(supplier_data.get("customer_number"))
        name = supplier_data.get("name") or ""
        if not customer_number and not self.normalize(name):
            return None
        candidates = []
        for supplier in self._suppliers or []:
            number = self.compact(supplier.customer_number)
            if customer_number and number and customer_number == number:
                return {"supplier_id": supplier.id, "supplier_name": supplier.name, "confidence": 1.0, "method": "CUSTOMER_NUMBER", "decision": "AUTO_MATCH"}
            score = self._text_score(name, supplier.name)
            if score > 0:
                candidates.append((score, supplier))
        candidates.sort(key=lambda row: row[0], reverse=True)
        if not candidates:
            return None
        score, supplier = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else 0.0
        if score < 0.75 or (second_score >= 0.75 and score - second_score < 0.08):
            return {"supplier_id": None, "supplier_name": supplier.name, "confidence": round(score, 4), "method": "NAME_SIMILARITY", "decision": "REVIEW"}
        return {"supplier_id": supplier.id, "supplier_name": supplier.name, "confidence": round(score, 4), "method": "NAME_SIMILARITY", "decision": "AUTO_MATCH" if score >= 0.93 else "REVIEW"}

    def match_line(self, extracted: dict, limit: int = 3, supplier_id: int | None = None):
        self._load_catalog()
        scored = []
        for product in self._products or []:
            score, method = self._candidate_score(extracted, product, supplier_id=supplier_id)
            if score >= 0.45:
                scored.append((score, method, product))
        scored.sort(key=lambda row: (-row[0], row[2].id))
        suggestions = [{
            "product_id": product.id,
            "product_name": product.name,
            "supplier_id": product.supplier_id,
            "supplier_name": product.supplier.name if product.supplier else None,
            "confidence": round(score, 4),
            "method": method,
        } for score, method, product in scored[: max(1, limit)]]
        best = suggestions[0] if suggestions else None
        if best is None:
            decision = "NO_MATCH"
        elif best["confidence"] >= 0.93:
            decision = "AUTO_MATCH"
        elif best["confidence"] >= 0.75:
            decision = "REVIEW"
        else:
            decision = "LOW_CONFIDENCE"
        return {"decision": decision, "best_match": best, "suggestions": suggestions}

    def _build_supplier_sections(self, data: dict) -> list[dict]:
        raw_sections = data.get("supplier_sections")
        sections: list[dict] = []
        if isinstance(raw_sections, list):
            for raw in raw_sections:
                if not isinstance(raw, dict):
                    continue
                supplier = raw.get("supplier") if isinstance(raw.get("supplier"), dict) else {}
                items = raw.get("items") if isinstance(raw.get("items"), list) else []
                section = {"supplier": dict(supplier), "items": [dict(item) for item in items if isinstance(item, dict)]}
                if isinstance(raw.get("page_numbers"), list):
                    section["page_numbers"] = list(raw["page_numbers"])
                sections.append(section)
        if sections:
            return sections
        supplier = data.get("supplier") if isinstance(data.get("supplier"), dict) else {}
        items = data.get("items") if isinstance(data.get("items"), list) else []
        if items or supplier:
            return [{"supplier": dict(supplier), "items": [dict(item) for item in items if isinstance(item, dict)]}]
        return []

    def enrich_document(self, data: dict) -> dict:
        """Attach supplier-aware, non-destructive catalog suggestions to extracted document data."""
        if not isinstance(data, dict):
            return data
        self._load_catalog()
        sections = self._build_supplier_sections(data)
        enriched_sections = []
        flat_items = []
        matched_suppliers = []

        for section_index, section in enumerate(sections):
            supplier_data = section.get("supplier") or {}
            supplier_match = self.match_supplier(supplier_data)
            supplier_id = supplier_match.get("supplier_id") if supplier_match and supplier_match.get("supplier_id") else None
            section_items = []
            for raw_item in section.get("items") or []:
                item = dict(raw_item)
                item["supplier_section_index"] = section_index
                item["supplier_context"] = dict(supplier_data)
                item["supplier_matching"] = supplier_match
                item["product_matching"] = self.match_line(item, supplier_id=supplier_id)
                section_items.append(item)
                flat_items.append(item)
            enriched = {"supplier": dict(supplier_data), "items": section_items, "supplier_matching": supplier_match}
            if isinstance(section.get("page_numbers"), list):
                enriched["page_numbers"] = section["page_numbers"]
            enriched_sections.append(enriched)
            matched_suppliers.append(supplier_match)

        data["supplier_sections"] = enriched_sections
        data["items"] = flat_items
        if len(enriched_sections) == 1:
            data["supplier"] = enriched_sections[0].get("supplier") or data.get("supplier")
            data["supplier_matching"] = enriched_sections[0].get("supplier_matching")
        else:
            data.pop("supplier", None)
            data["supplier_matching"] = matched_suppliers
        data["supplier_count"] = len(enriched_sections)
        data["matching_version"] = "deterministic-v2-multi-supplier"
        return data
