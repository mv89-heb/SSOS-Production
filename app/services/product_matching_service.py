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
        "חלבי", "פרווה", "במשקל", "קפוא", "קפואה", "קפואים", "לשוק", "חיצוני",
        "מחיר", "לקג", "מוסדי", "בטעם", "מוצר",
    }

    SUPPLIER_STOP_WORDS = {
        "בעמ", 'בע"מ', "חברה", "חברות", "תעשיות", "תעשיה", "יבוא", "ושיווק",
        "שיווק", "מסחר", "מסחרית",
    }

    # Attributes that distinguish catalog identities. A fuzzy score must never
    # override a conflict in one of these explicit attributes.
    ITEM_TYPE_GROUPS = {
        "utensil": {
            "כף": "spoon", "כפות": "spoon", "כפית": "teaspoon", "כפיות": "teaspoon",
            "מזלג": "fork", "מזלגות": "fork", "סכין": "knife", "סכינים": "knife",
        },
        "dishware": {
            "צלחת": "plate", "צלחות": "plate", "קערה": "bowl", "קעריות": "bowl",
            "קערית": "bowl", "קעריות": "bowl", "מגש": "tray", "מגשים": "tray",
            "כוס": "cup", "כוסות": "cup", "ספל": "mug", "ספלים": "mug",
        },
        "paper_goods": {
            "מפית": "napkin", "מפיות": "napkin", "מגבת": "towel", "מגבות": "towel",
            "טואלט": "toilet_paper", "נייר": "paper",
        },
    }
    VARIANT_GROUPS = {
        "size": {
            "גדול": "large", "גדולה": "large", "גדולים": "large", "גדולות": "large",
            "קטן": "small", "קטנה": "small", "קטנים": "small", "קטנות": "small",
            "ענק": "giant", "ענקית": "giant", "בינוני": "medium", "בינונית": "medium",
        },
        "color": {
            "לבן": "white", "לבנה": "white", "לבנים": "white", "לבנות": "white",
            "שחור": "black", "שחורה": "black", "שחורים": "black", "שחורות": "black",
            "שקוף": "transparent", "שקופה": "transparent", "שקופים": "transparent", "שקופות": "transparent",
            "קרם": "cream", "זהב": "gold", "זהובה": "gold", "כסף": "silver",
            "כסופה": "silver", "כחול": "blue", "כחולה": "blue", "אדום": "red", "אדומה": "red",
            "ירוק": "green", "ירוקה": "green",
        },
        "use": {
            "מרק": "soup", "סלטיות": "salad_bowls", "סלטיה": "salad_bowl",
            "חלונות": "windows", "אסלות": "toilet", "רצפות": "floor",
        },
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
        text = text.replace('תפו"ע', 'תפוח עץ').replace('תפו"א', 'תפוח אדמה').replace("מאפינס", "מאפין")
        text = text.replace("\u05f3", "'").replace("\u05f4", '"')
        text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text)
        text = re.sub(r"[^\w\u0590-\u05ff\"]+", " ", text, flags=re.UNICODE)
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
            overlap = len(at & bt)
            coverage = overlap / max(len(at), len(bt))
            containment = overlap / min(len(at), len(bt))
            return max(sequence, coverage, containment if containment >= 0.9 else 0.0)
        return sequence

    @classmethod
    def _supplier_name_score(cls, extracted_name, catalog_name) -> tuple[float, str]:
        extracted_tokens = {t for t in cls.normalize(extracted_name).split() if len(t) > 1 and t not in cls.SUPPLIER_STOP_WORDS}
        catalog_tokens = {t for t in cls.normalize(catalog_name).split() if len(t) > 1 and t not in cls.SUPPLIER_STOP_WORDS}
        if not extracted_tokens or not catalog_tokens:
            return cls._text_score(extracted_name, catalog_name), "NAME_SIMILARITY"
        overlap = len(extracted_tokens & catalog_tokens)
        if catalog_tokens <= extracted_tokens or extracted_tokens <= catalog_tokens:
            return 1.0, "NAME_CORE"
        coverage = overlap / max(len(extracted_tokens), len(catalog_tokens))
        containment = overlap / min(len(extracted_tokens), len(catalog_tokens))
        return max(coverage, containment if containment >= 0.8 else 0.0, cls._text_score(extracted_name, catalog_name)), "NAME_SIMILARITY"

    @classmethod
    def _is_synthetic_barcode(cls, value) -> bool:
        return bool(re.fullmatch(r"990000010000\d+", cls.compact(value)))

    @classmethod
    def _identity_score(cls, extracted, product) -> tuple[float, str | None]:
        barcode = cls.compact(extracted.get("barcode"))
        product_barcode = cls.compact(product.barcode)
        if barcode and product_barcode and barcode == product_barcode:
            # Generated inventory labels are not supplier identities.
            if not ProductMatchingService._is_synthetic_barcode(barcode) and not ProductMatchingService._is_synthetic_barcode(product_barcode):
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
    def _measure_signature(cls, value) -> tuple[str, float] | None:
        raw = unicodedata.normalize("NFKC", str(value or "")).casefold()
        raw = raw.replace("\u05f4", '"').replace("\u05f3", "'")
        match = re.search(
            r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(millilit(?:er|re)s?|ml|מיליליטר|מ[\"']?ל|"
            r"lit(?:er|re)s?|l|ליטרים?|ליטר|kg|kgs?|ק\s*ג|קילו(?:גרם)?|g|גרם|"
            r"cm|סמ|ס\s*מ|mm|ממ|מ\s*מ|מטרים?|מטר)(?!\w)",
            raw,
        )
        if not match:
            return None
        amount = float(match.group(1).replace(",", "."))
        unit = re.sub(r"\s+", "", match.group(2))
        if unit in {"l", "liter", "liters", "litre", "litres", "ליטר", "ליטרים"}:
            return "volume_ml", amount * 1000
        if unit in {"ml", "milliliter", "milliliters", "millilitre", "millilitres", "מיליליטר", 'מל', 'מ"ל'}:
            return "volume_ml", amount
        if unit in {"kg", "kgs", "קג", "קילו", "קילוגרם"}:
            return "mass_g", amount * 1000
        if unit in {"g", "גרם"}:
            return "mass_g", amount
        if unit in {"cm", "סמ"}:
            return "length_mm", amount * 10
        if unit in {"mm", "ממ"}:
            return "length_mm", amount
        if unit in {"מטר", "מטרים"}:
            return "length_mm", amount * 1000
        return None

    @classmethod
    def _percent_signature(cls, value) -> float | None:
        raw = unicodedata.normalize("NFKC", str(value or "")).casefold()
        raw = raw.replace("\u05f4", '"').replace("\u05f3", "'")
        match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:%|אחוז(?:ים)?)(?!\w)", raw)
        return float(match.group(1).replace(",", ".")) if match else None

    @classmethod
    def _package_count(cls, value) -> int | None:
        raw = unicodedata.normalize("NFKC", str(value or "")).casefold()
        match = re.search(r"(?<!\d)(\d+)\s*(?:יח(?:ידות|ידה|י|׳|')?|pcs?|pieces)(?!\w)", raw)
        return int(match.group(1)) if match else None

    @classmethod
    def _variant_conflict(cls, extracted, product) -> bool:
        """Reject explicit contradictions before identity shortcuts or fuzzy scoring."""
        source_tokens = cls.tokens(extracted.get("description"))
        catalog_tokens = cls.tokens(product.name)

        source_measure = cls._measure_signature(extracted.get("description"))
        catalog_measure = cls._measure_signature(product.name)
        if source_measure is not None and catalog_measure is not None and source_measure != catalog_measure:
            return True
        source_percent = cls._percent_signature(extracted.get("description"))
        catalog_percent = cls._percent_signature(product.name)
        if source_percent is not None and catalog_percent is not None and source_percent != catalog_percent:
            return True
        source_count = cls._package_count(extracted.get("description"))
        catalog_count = cls._package_count(product.name)
        if source_count is not None and catalog_count is not None and source_count != catalog_count:
            return True

        source_types = set()
        catalog_types = set()
        for group_name, attribute_map in cls.ITEM_TYPE_GROUPS.items():
            source_types.update((group_name, attribute_map[token]) for token in source_tokens if token in attribute_map)
            catalog_types.update((group_name, attribute_map[token]) for token in catalog_tokens if token in attribute_map)
        if source_types and catalog_types and source_types.isdisjoint(catalog_types):
            return True

        for group in (cls.ITEM_TYPE_GROUPS, cls.VARIANT_GROUPS):
            for attribute_map in group.values():
                source_values = {attribute_map[token] for token in source_tokens if token in attribute_map}
                catalog_values = {attribute_map[token] for token in catalog_tokens if token in attribute_map}
                if source_values and catalog_values and source_values.isdisjoint(catalog_values):
                    return True
        return False

    @classmethod
    def _variant_unconfirmed(cls, extracted, product) -> bool:
        """Flag a candidate for review when the line has attributes the catalog omits."""
        source_tokens = cls.tokens(extracted.get("description"))
        catalog_tokens = cls.tokens(product.name)
        if cls._measure_signature(extracted.get("description")) is not None and cls._measure_signature(product.name) is None:
            return True
        if cls._percent_signature(extracted.get("description")) is not None and cls._percent_signature(product.name) is None:
            return True
        if cls._package_count(extracted.get("description")) is not None and cls._package_count(product.name) is None:
            return True
        for group in (cls.ITEM_TYPE_GROUPS, cls.VARIANT_GROUPS):
            for attribute_map in group.values():
                source_values = {attribute_map[token] for token in source_tokens if token in attribute_map}
                catalog_values = {attribute_map[token] for token in catalog_tokens if token in attribute_map}
                if source_values and not catalog_values:
                    return True
                if source_values and catalog_values and source_values != catalog_values:
                    return True
        return False

    @classmethod
    def _candidate_score(cls, extracted, product, supplier_id: int | None = None) -> tuple[float, str]:
        if cls._variant_conflict(extracted, product):
            return 0.0, "PRODUCT_VARIANT_MISMATCH"
        unconfirmed_variant = cls._variant_unconfirmed(extracted, product)
        identity, method = cls._identity_score(extracted, product)
        if identity:
            # Identity data is strong evidence, but an omitted explicit variant
            # must keep the line in manual review rather than auto-select it.
            return (min(identity, 0.89), "IDENTITY_VARIANT_UNCONFIRMED") if unconfirmed_variant else (identity, method)
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
        if unconfirmed_variant:
            score = min(score, 0.89)
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
            score, method = self._supplier_name_score(name, supplier.name)
            if score > 0:
                candidates.append((score, method, supplier))
        candidates.sort(key=lambda row: row[0], reverse=True)
        if not candidates:
            return None
        score, method, supplier = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else 0.0
        if second_score >= 0.75 and score - second_score < 0.08:
            return {"supplier_id": None, "supplier_name": name, "confidence": round(score, 4), "method": method, "decision": "REVIEW"}
        if method == "NAME_CORE":
            return {"supplier_id": supplier.id, "supplier_name": supplier.name, "confidence": 1.0, "method": method, "decision": "AUTO_MATCH"}
        if score < 0.75:
            return {"supplier_id": None, "supplier_name": name, "confidence": round(score, 4), "method": method, "decision": "REVIEW"}
        return {"supplier_id": supplier.id, "supplier_name": supplier.name, "confidence": round(score, 4), "method": method, "decision": "AUTO_MATCH" if score >= 0.88 else "REVIEW"}

    def match_line(self, extracted: dict, limit: int = 3, supplier_id: int | None = None):
        self._load_catalog()
        scored = []
        catalog = self._products or []
        if supplier_id is not None:
            supplier_catalog = [product for product in catalog if product.supplier_id == supplier_id]
            catalog = supplier_catalog or catalog
        for product in catalog:
            score, method = self._candidate_score(extracted, product, supplier_id=supplier_id)
            if score >= 0.45:
                scored.append((score, method, product))
        scored.sort(key=lambda row: (-row[0], row[2].id))
        suggestions = [
            {"product_id": product.id, "product_name": product.name, "supplier_id": product.supplier_id, "supplier_name": product.supplier.name if product.supplier else None, "confidence": round(score, 4), "method": method}
            for score, method, product in scored[: max(1, limit)]
        ]
        candidate = suggestions[0] if suggestions else None
        if candidate is None:
            return {"decision": "NO_MATCH", "best_match": None, "suggestions": []}

        confidence = candidate["confidence"]
        if confidence >= 0.93:
            decision = "AUTO_MATCH"
            best = candidate
        elif confidence >= 0.75:
            decision = "REVIEW"
            best = candidate
        else:
            # Keep low-confidence candidates as suggestions for human review, but
            # never present a weak fuzzy match as the selected product. This is
            # especially important for generic invoice rows such as packaging.
            decision = "LOW_CONFIDENCE"
            best = None

        if best is not None:
            best["decision"] = decision
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
