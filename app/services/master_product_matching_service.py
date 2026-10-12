from __future__ import annotations

import math
import re
import unicodedata

from rapidfuzz import fuzz

from sqlalchemy import select
from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.models.master_product import MasterProduct
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from app.services.audit_service import AuditService


class MasterProductMatchingService:
    """Tenant-scoped intake, candidate scoring and human approval for supplier SKUs."""

    AUTO_SUGGEST_THRESHOLD = 0.94
    REVIEW_THRESHOLD = 0.62
    UNIT_ALIASES = {
        "litre": "l", "liter": "l", "litres": "l", "ליטר": "l", "ליטרים": "l",
        "ml": "ml", "מיליליטר": "ml", "מ״ל": "ml", 'מ"ל': "ml",
        "kg": "kg", "kgs": "kg", "קג": "kg", 'ק"ג': "kg", "קילו": "kg", "קילוגרם": "kg",
        "g": "g", "גרם": "g", "gr": "g",
        "unit": "unit", "piece": "unit", "pieces": "unit", "יח": "unit", "יחידה": "unit", "יחידות": "unit",
        "pack": "pack", "package": "pack", "מארז": "pack", "אריזה": "pack",
    }
    SIZE_PATTERN = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(ml|l|kg|g|מיליליטר|ליטרים?|קג|קילו|גרם)(?!\w)", re.I)
    PERCENT_PATTERN = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:%|אחוז(?:ים)?)(?!\w)", re.I)

    def __init__(self, tenant_id: int, user_id: int | None = None):
        self.tenant_id = int(tenant_id)
        self.user_id = user_id

    @classmethod
    def normalize(cls, value) -> str:
        if value is None:
            return ""
        text = unicodedata.normalize("NFKC", str(value)).casefold()
        text = text.replace("תפו״ע", "תפוח עץ").replace('תפו"ע', "תפוח עץ")
        text = text.replace("תפו״א", "תפוח אדמה").replace('תפו"א', "תפוח אדמה")
        text = text.replace("\u05f3", "'").replace("\u05f4", '"')
        text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text)
        text = re.sub(r"(\d)\s*(?:אחוז(?:ים)?)", r"\1%", text)
        text = re.sub(r"(\d+(?:[.,]\d+)?)\s*(ml|l|kg|g)\b", r"\1 \2", text)
        # Keep % and decimal points because fat percentage and package size are identity attributes.
        text = re.sub(r"[^\w\u0590-\u05ff.%]+", " ", text, flags=re.UNICODE)
        text = re.sub(r"(?<=\d),(?=\d)", ".", text)
        text = re.sub(r"\s+", " ", text).strip(" .")
        tokens = []
        for token in text.split():
            tokens.append(cls.UNIT_ALIASES.get(token, token))
        return " ".join(tokens)

    @classmethod
    def _signature(cls, value: str) -> tuple[float | None, str | None, float | None]:
        normalized = cls.normalize(value)
        size = cls.SIZE_PATTERN.search(normalized)
        size_value = None
        size_unit = None
        if size:
            size_value = float(size.group(1).replace(",", "."))
            size_unit = cls.UNIT_ALIASES.get(size.group(2).casefold(), size.group(2).casefold())
            if size_unit == "l":
                size_value *= 1000
                size_unit = "ml"
            elif size_unit == "kg":
                size_value *= 1000
                size_unit = "g"
        percent = cls.PERCENT_PATTERN.search(normalized)
        percent_value = float(percent.group(1).replace(",", ".")) if percent else None
        return size_value, size_unit, percent_value

    @classmethod
    def _score(cls, query: str, candidate: str) -> tuple[float, str | None]:
        left, right = cls.normalize(query), cls.normalize(candidate)
        if not left or not right:
            return 0.0, "EMPTY_NAME"
        left_size, left_unit, left_pct = cls._signature(left)
        right_size, right_unit, right_pct = cls._signature(right)
        if left_size is not None and right_size is not None and (left_unit != right_unit or abs(left_size - right_size) > 0.0001):
            return 0.0, "PACKAGE_SIZE_MISMATCH"
        if left_pct is not None and right_pct is not None and abs(left_pct - right_pct) > 0.0001:
            return 0.0, "PRODUCT_VARIANT_MISMATCH"

        sequence = fuzz.ratio(left, right) / 100
        token_score = fuzz.token_set_ratio(left, right) / 100
        left_tokens, right_tokens = set(left.split()), set(right.split())
        overlap = len(left_tokens & right_tokens)
        containment = overlap / min(len(left_tokens), len(right_tokens)) if left_tokens and right_tokens else 0
        score = max(sequence, token_score, containment * 0.92)
        # A matching package/variant is useful corroboration, never enough on its own.
        if left_size is not None and left_size == right_size and left_unit == right_unit:
            score = min(1.0, score + 0.025)
        if left_pct is not None and left_pct == right_pct:
            score = min(1.0, score + 0.025)
        return round(score, 4), "FUZZY_TEXT"

    @staticmethod
    def _is_synthetic_barcode(value) -> bool:
        return bool(re.fullmatch(r"990000010000\d+", re.sub(r"\D", "", str(value or ""))))

    def _supplier(self, supplier_id: int) -> Supplier:
        supplier = db.session.execute(select(Supplier).where(
            Supplier.id == supplier_id, Supplier.tenant_id == self.tenant_id, Supplier.active.is_(True)
        )).scalar_one_or_none()
        if supplier is None:
            raise NotFound("הספק לא נמצא או שאינו פעיל")
        return supplier

    def suggest(self, name: str, barcode: str | None = None, limit: int = 5):
        normalized = self.normalize(name)
        if not normalized:
            return []
        masters = db.session.execute(select(MasterProduct).where(
            MasterProduct.tenant_id == self.tenant_id, MasterProduct.active.is_(True)
        )).scalars().all()
        candidates = []
        clean_barcode = re.sub(r"\D", "", str(barcode or ""))
        if clean_barcode and not self._is_synthetic_barcode(clean_barcode):
            exact = [m for m in masters if re.sub(r"\D", "", str(m.barcode or "")) == clean_barcode and m.barcode]
            if len(exact) == 1:
                return [{"master_product": exact[0].to_dict(), "confidence": 1.0, "method": "EXACT_BARCODE", "decision": "SAFE_AUTO_LINK"}]
        for master in masters:
            score, method = self._score(normalized, master.canonical_name)
            if score >= self.REVIEW_THRESHOLD:
                candidates.append((score, method, master))
        candidates.sort(key=lambda item: (-item[0], item[2].id))
        result = []
        for index, (score, method, master) in enumerate(candidates[:max(1, min(int(limit), 10))]):
            next_score = candidates[index + 1][0] if index + 1 < len(candidates) else 0.0
            decision = "HIGH_CONFIDENCE_SUGGESTION" if score >= self.AUTO_SUGGEST_THRESHOLD and score - next_score >= 0.06 else "REVIEW"
            result.append({"master_product": master.to_dict(), "confidence": score, "method": method, "decision": decision})
        return result

    def intake(self, data: dict) -> tuple[SupplierProduct, list[dict]]:
        if not isinstance(data, dict):
            raise BadRequest("נדרש גוף בקשה תקין")
        supplier_id = data.get("supplier_id")
        try:
            supplier_id = int(supplier_id)
        except (TypeError, ValueError):
            raise BadRequest("יש לבחור ספק תקין")
        supplier = self._supplier(supplier_id)
        name = str(data.get("supplier_name") or data.get("name") or data.get("description") or "").strip()
        if not name:
            raise BadRequest("שם מוצר הספק הוא שדה חובה")
        raw_price = data.get("price")
        price = None
        if raw_price not in (None, ""):
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                raise BadRequest("המחיר חייב להיות מספר חיובי")
            if not math.isfinite(price) or price <= 0:
                raise BadRequest("המחיר חייב להיות מספר סופי וגדול מאפס")
        currency = str(data.get("currency") or "ILS").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise BadRequest("יש להזין קוד מטבע תקין בן שלוש אותיות")
        carton_value = data.get("units_per_carton")
        if carton_value not in (None, ""):
            try:
                carton_value = int(carton_value)
            except (TypeError, ValueError):
                raise BadRequest("מספר היחידות באריזה חייב להיות מספר שלם וחיובי")
            if carton_value <= 0 or str(data.get("units_per_carton")).strip() != str(carton_value):
                raise BadRequest("מספר היחידות באריזה חייב להיות מספר שלם וחיובי")
        else:
            carton_value = None
        sku = str(data.get("supplier_sku") or "").strip() or None
        if sku:
            existing = db.session.execute(select(SupplierProduct).where(
                SupplierProduct.tenant_id == self.tenant_id,
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.supplier_sku == sku,
            )).scalars().first()
            if existing:
                if existing.match_status == "APPROVED":
                    existing.supplier_name = name
                    existing.description = data.get("description") or name
                    existing.barcode = str(data.get("barcode") or "").strip() or existing.barcode
                    existing.price = price if price is not None else existing.price
                    existing.currency = currency
                    existing.unit = data.get("unit") or existing.unit
                    existing.units_per_carton = carton_value or existing.units_per_carton
                    existing.normalized_name = self.normalize(name)
                    existing.last_seen_at = db.func.now()
                    db.session.flush()
                    return existing, []
                # Refresh a pending supplier item instead of creating duplicate review tasks.
                existing.supplier_name = name
                existing.description = data.get("description") or name
                existing.barcode = str(data.get("barcode") or "").strip() or None
                existing.price = price
                existing.currency = currency
                existing.unit = data.get("unit")
                existing.units_per_carton = carton_value
                existing.normalized_name = self.normalize(name)
                existing.last_seen_at = db.func.now()
                existing.match_status = "PENDING"
                existing.master_product_id = None
                item = existing
            else:
                item = None
        else:
            item = None
        suggestions = self.suggest(name, data.get("barcode"))
        safe = suggestions[0] if suggestions and suggestions[0]["decision"] == "SAFE_AUTO_LINK" else None
        best = suggestions[0] if suggestions else None
        if item is None:
            item = SupplierProduct(
                tenant_id=self.tenant_id, supplier_id=supplier_id, supplier_name=name,
                description=str(data.get("description") or name), supplier_sku=sku,
                barcode=str(data.get("barcode") or "").strip() or None, price=price,
                currency=currency, unit=str(data.get("unit") or "").strip() or None,
                units_per_carton=carton_value, normalized_name=self.normalize(name),
                match_status="APPROVED" if safe else "PENDING",
                master_product_id=safe["master_product"]["id"] if safe else None,
                suggested_master_product_id=best["master_product"]["id"] if best and not safe else None,
                match_confidence=safe["confidence"] if safe else (best["confidence"] if best else None),
                match_method=safe["method"] if safe else (best["method"] if best else "NO_CANDIDATE"),
            )
            db.session.add(item)
        elif item.match_status != "APPROVED":
            if safe:
                item.master_product_id = safe["master_product"]["id"]
                item.suggested_master_product_id = safe["master_product"]["id"]
                item.match_status = "APPROVED"
                item.match_confidence = safe["confidence"]
                item.match_method = safe["method"]
            else:
                item.master_product_id = None
                item.match_status = "PENDING"
                item.suggested_master_product_id = best["master_product"]["id"] if best else None
                item.match_confidence = best["confidence"] if best else None
                item.match_method = best["method"] if best else "NO_CANDIDATE"
        db.session.flush()
        AuditService.log_event(self.tenant_id, self.user_id, "supplier_product.intake", "נוסף פריט מחירון ספק", {
            "supplier_product_id": item.id, "supplier_id": supplier_id,
            "master_product_id": item.master_product_id, "match_status": item.match_status,
        })
        return item, suggestions

    def pending(self, limit: int = 100):
        limit = max(1, min(int(limit), 250))
        return db.session.execute(select(SupplierProduct).where(
            SupplierProduct.tenant_id == self.tenant_id,
            SupplierProduct.match_status == "PENDING",
        ).order_by(SupplierProduct.created_at.asc(), SupplierProduct.id.asc()).limit(limit)).scalars().all()

    def approve(self, supplier_product_id: int, master_product_id: int):
        item = db.session.execute(select(SupplierProduct).where(
            SupplierProduct.id == supplier_product_id, SupplierProduct.tenant_id == self.tenant_id
        )).scalar_one_or_none()
        if item is None:
            raise NotFound("פריט הספק לא נמצא")
        master = db.session.execute(select(MasterProduct).where(
            MasterProduct.id == master_product_id, MasterProduct.tenant_id == self.tenant_id,
            MasterProduct.active.is_(True),
        )).scalar_one_or_none()
        if master is None:
            raise NotFound("מוצר האב לא נמצא")
        item.master_product_id = master.id
        item.suggested_master_product_id = master.id
        item.match_status = "APPROVED"
        item.match_method = "MANUAL_APPROVAL"
        item.match_confidence = 1
        db.session.flush()
        AuditService.log_event(self.tenant_id, self.user_id, "supplier_product.match_approved", "אושר שיוך מוצר ספק למוצר אב", {
            "supplier_product_id": item.id, "master_product_id": master.id,
        })
        return item

    def create_master_and_approve(self, supplier_product_id: int, data: dict):
        item = db.session.execute(select(SupplierProduct).where(
            SupplierProduct.id == supplier_product_id, SupplierProduct.tenant_id == self.tenant_id
        )).scalar_one_or_none()
        if item is None:
            raise NotFound("פריט הספק לא נמצא")
        name = str((data or {}).get("canonical_name") or item.supplier_name).strip()
        if not name:
            raise BadRequest("שם מוצר האב הוא שדה חובה")
        normalized = self.normalize(name)
        raw_package_size = (data or {}).get("package_size")
        package_size = None
        if raw_package_size not in (None, ""):
            try:
                package_size = float(raw_package_size)
            except (TypeError, ValueError):
                raise BadRequest("גודל האריזה חייב להיות מספר חיובי")
            if not math.isfinite(package_size) or package_size <= 0:
                raise BadRequest("גודל האריזה חייב להיות מספר חיובי")
            if not str((data or {}).get("package_unit") or "").strip():
                raise BadRequest("יש לציין יחידת מידה לגודל האריזה")
        master = MasterProduct(
            tenant_id=self.tenant_id, canonical_name=name, normalized_name=normalized,
            brand=str((data or {}).get("brand") or "").strip() or None,
            category=str((data or {}).get("category") or "").strip() or None,
            barcode=str((data or {}).get("barcode") or item.barcode or "").strip() or None,
            base_unit=str((data or {}).get("base_unit") or item.unit or "").strip() or None,
            package_size=package_size,
            package_unit=str((data or {}).get("package_unit") or "").strip() or None,
        )
        db.session.add(master)
        db.session.flush()
        item.master_product_id = master.id
        item.suggested_master_product_id = master.id
        item.match_status = "APPROVED"
        item.match_method = "NEW_MASTER_CREATED"
        item.match_confidence = 1
        db.session.flush()
        AuditService.log_event(self.tenant_id, self.user_id, "master_product.created_from_supplier", "נוצר מוצר אב ואושר שיוך", {
            "supplier_product_id": item.id, "master_product_id": master.id,
        })
        return item, master


    def compare_master_product(self, master_product_id: int):
        from decimal import Decimal
        from app.services.price_intelligence_service import PriceIntelligenceService

        master = db.session.execute(select(MasterProduct).where(
            MasterProduct.id == master_product_id,
            MasterProduct.tenant_id == self.tenant_id,
            MasterProduct.active.is_(True),
        )).scalar_one_or_none()
        if master is None:
            raise NotFound("מוצר האב לא נמצא")

        listings = db.session.execute(
            select(SupplierProduct).join(
                Supplier,
                (Supplier.id == SupplierProduct.supplier_id) & (Supplier.tenant_id == self.tenant_id),
            ).where(
                SupplierProduct.tenant_id == self.tenant_id,
                SupplierProduct.master_product_id == master.id,
                SupplierProduct.match_status == "APPROVED",
                SupplierProduct.active.is_(True),
            ).order_by(SupplierProduct.id.asc())
        ).scalars().all()

        groups = {}
        incomplete = []
        for listing in listings:
            if listing.price is None or Decimal(str(listing.price)) <= 0:
                incomplete.append({**listing.to_dict(), "incomparable_reason": "חסר מחיר חיובי"})
                continue
            row = PriceIntelligenceService._price_payload(
                listing.supplier_id,
                listing.supplier.name if listing.supplier else None,
                listing.price, listing.unit, listing.units_per_carton,
                listing.currency, primary=False,
            )
            row.update({
                "supplier_product_id": listing.id,
                "supplier_sku": listing.supplier_sku,
                "supplier_product_name": listing.supplier_name,
            })
            if row["comparison_unit"] is None:
                incomplete.append({**row, "incomparable_reason": "חסרה יחידת השוואה או כמות באריזה"})
                continue
            key = (row["currency"], row["comparison_unit"])
            groups.setdefault(key, []).append(row)

        formatted_groups = []
        for (currency, unit), offers in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
            offers.sort(key=lambda row: (row["normalized_price"], row["supplier_name"] or ""))
            formatted_groups.append({
                "currency": currency,
                "comparison_unit": unit,
                "offers": offers,
                "best_offer": offers[0] if offers else None,
            })
        return {
            "master_product": master.to_dict(),
            "groups": formatted_groups,
            "incomplete_offers": incomplete,
            "supplier_product_count": len(listings),
        }
