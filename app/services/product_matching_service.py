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
        return {
            token for token in cls.normalize(value).split()
            if len(token) > 1 and token not in cls.STOP_WORDS
        }

    @classmethod
    def _text_score(cls, left, right) -> float:
        a, b = cls.normalize(left), cls.normalize(right)
        if not a or not b:
            return 0.0
        sequence = SequenceMatcher(None, a, b).ratio()
        at, bt = cls.tokens(a), cls.tokens(b)
        if at and bt:
            overlap = len(at & bt) / max(len(at), len(bt))
            return max(sequence, overlap)
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
        name_score = cls._text_score(description, product.name)
        description_score = cls._text_score(description, product.description)
        score = max(name_score, description_score * 0.92)

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
            self._products = list(
                Product.query.filter_by(tenant_id=self.tenant_id, active=True).all()
            )
        if self._suppliers is None:
            self._suppliers = list(
                Supplier.query.filter_by(tenant_id=self.tenant_id, active=True).all()
            )

    def match_supplier(self, supplier_data: dict | None):
        self._load_catalog()
        supplier_data = supplier_data or {}
        customer_number = self.compact(supplier_data.get("customer_number"))
        name = supplier_data.get("name") or ""
        candidates = []
        for supplier in self._suppliers or []:
            number = self.compact(supplier.customer_number)
            if customer_number and number and customer_number == number:
                return {
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "confidence": 1.0,
                    "method": "CUSTOMER_NUMBER",
                }
            score = self._text_score(name, supplier.name)
            if score > 0:
                candidates.append((score, supplier))
        candidates.sort(key=lambda row: row[0], reverse=True)
        if not candidates:
            return None
        score, supplier = candidates[0]
        return {
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "confidence": round(score, 4),
            "method": "NAME_SIMILARITY",
        }

    def match_line(self, extracted: dict, limit: int = 3, supplier_id: int | None = None):
        self._load_catalog()
        scored = []
        for product in self._products or []:
            score, method = self._candidate_score(extracted, product, supplier_id=supplier_id)
            if score >= 0.45:
                scored.append((score, method, product))
        scored.sort(key=lambda row: (-row[0], row[2].id))
        suggestions = []
        for score, method, product in scored[: max(1, limit)]:
            suggestions.append({
                "product_id": product.id,
                "product_name": product.name,
                "supplier_id": product.supplier_id,
                "supplier_name": product.supplier.name if product.supplier else None,
                "confidence": round(score, 4),
                "method": method,
            })
        best = suggestions[0] if suggestions else None
        if best is None:
            decision = "NO_MATCH"
        elif best["confidence"] >= 0.93:
            decision = "AUTO_MATCH"
        elif best["confidence"] >= 0.75:
            decision = "REVIEW"
        else:
            decision = "LOW_CONFIDENCE"
        return {
            "decision": decision,
            "best_match": best,
            "suggestions": suggestions,
        }

    def enrich_document(self, data: dict) -> dict:
        """Attach non-destructive catalog suggestions to extracted document data."""
        if not isinstance(data, dict):
            return data
        self._load_catalog()
        supplier_match = self.match_supplier(data.get("supplier"))
        supplier_id = supplier_match.get("supplier_id") if supplier_match else None
        items = data.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    item["product_matching"] = self.match_line(item, supplier_id=supplier_id)
        data["supplier_matching"] = supplier_match
        data["matching_version"] = "deterministic-v1"
        return data
