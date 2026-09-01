from decimal import Decimal, InvalidOperation

from app.repositories.product_repository import ProductRepository
from app.repositories.price_history_repository import PriceHistoryRepository


class PriceIntelligenceService:
    """Deterministic supplier-price comparison and savings calculations.

    AI is deliberately not used here. AI/document extraction can populate
    supplier offers and observations later; this service owns the arithmetic
    and comparison rules so financial results remain reproducible.
    """

    UNIT_ALIASES = {
        "unit": "UNIT", "units": "UNIT", "piece": "UNIT", "pieces": "UNIT",
        "יח": "UNIT", "יחידה": "UNIT", "יחידות": "UNIT", "פריט": "UNIT",
        "kg": "KG", "kgs": "KG", "קג": "KG", "ק"ג": "KG", "קילו": "KG", "קילוגרם": "KG",
        "g": "G", "גרם": "G",
        "liter": "L", "litre": "L", "l": "L", "ליטר": "L", "ליטרים": "L",
        "ml": "ML", "מיליליטר": "ML",
        "meter": "M", "m": "M", "מטר": "M",
        "pack": "PACK", "package": "PACK", "אריזה": "PACK", "מארז": "PACK",
        "carton": "CARTON", "case": "CARTON", "קרטון": "CARTON",
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.product_repo = ProductRepository(tenant_id)
        self.history_repo = PriceHistoryRepository(tenant_id)

    @staticmethod
    def _decimal(value) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def normalize_unit(cls, unit: str | None) -> str | None:
        if unit is None:
            return None
        value = str(unit).strip().casefold()
        if not value:
            return None
        return cls.UNIT_ALIASES.get(value, value.upper())

    @classmethod
    def normalize_offer_price(cls, price, unit, units_per_carton=None):
        """Return (normalized_price, comparison_unit).

        Carton prices are converted to unit prices only when the carton
        quantity is explicitly known. Missing unit metadata defaults to UNIT
        at comparison time when the product itself is unit-priced.
        """
        amount = cls._decimal(price)
        normalized = cls.normalize_unit(unit)
        cartons = cls._decimal(units_per_carton)
        if normalized == "CARTON" and cartons > 0:
            return amount / cartons, "UNIT"
        return amount, normalized

    @classmethod
    def _price_payload(cls, supplier_id, supplier_name, price, unit, units_per_carton, currency, *, primary=False):
        normalized_price, comparison_unit = cls.normalize_offer_price(price, unit, units_per_carton)
        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "price": float(cls._decimal(price)),
            "currency": currency,
            "unit": unit,
            "comparison_unit": comparison_unit,
            "normalized_price": float(normalized_price),
            "primary": primary,
        }

    def compare_product(self, product_id: int):
        product = self.product_repo.get_by_id_or_404(product_id)
        default_unit = self.normalize_unit(product.unit) or "UNIT"
        offers = []

        if product.current_price is not None and self._decimal(product.current_price) > 0:
            offers.append(self._price_payload(
                product.supplier_id,
                product.supplier.name if product.supplier else None,
                product.current_price,
                product.unit or default_unit,
                product.units_per_carton,
                product.currency,
                primary=True,
            ))

        for offer in product.supplier_offers:
            if not offer.active or self._decimal(offer.price) <= 0:
                continue
            offer_unit = offer.unit or product.unit or default_unit
            offers.append(self._price_payload(
                offer.supplier_id,
                offer.supplier.name if offer.supplier else None,
                offer.price,
                offer_unit,
                offer.units_per_carton,
                offer.currency,
            ))

        currencies = {row["currency"] for row in offers}
        comparable = []
        if len(currencies) == 1 and offers:
            units = {row["comparison_unit"] for row in offers}
            if len(units) == 1 and None not in units:
                comparable = offers

        comparable.sort(key=lambda row: row["normalized_price"])
        current = next((row for row in offers if row["primary"]), None)
        best = comparable[0] if comparable else None

        result = {
            "product": product.to_dict(),
            "current": current,
            "offers": comparable,
            "incomparable_offers": [row for row in offers if row not in comparable],
            "best_offer": best,
            "saving_per_unit": 0.0,
            "saving_percent": 0.0,
        }

        if current and best and current["normalized_price"] > 0:
            saving = current["normalized_price"] - best["normalized_price"]
            if saving > 0:
                result["saving_per_unit"] = round(saving, 4)
                result["saving_percent"] = round((saving / current["normalized_price"]) * 100, 4)

        return result

    def calculate_savings(self, product_id: int, quantity):
        comparison = self.compare_product(product_id)
        qty = self._decimal(quantity)
        current = comparison["current"]
        best = comparison["best_offer"]
        if qty <= 0 or not current or not best:
            return {
                "product_id": product_id,
                "quantity": float(qty),
                "current_cost": 0.0,
                "best_cost": 0.0,
                "savings": 0.0,
                "savings_percent": 0.0,
                "best_supplier_id": best["supplier_id"] if best else None,
            }

        current_cost = self._decimal(current["normalized_price"]) * qty
        best_cost = self._decimal(best["normalized_price"]) * qty
        savings = max(Decimal("0"), current_cost - best_cost)
        percent = (savings / current_cost * Decimal("100")) if current_cost > 0 else Decimal("0")
        return {
            "product_id": product_id,
            "quantity": float(qty),
            "current_cost": round(float(current_cost), 2),
            "best_cost": round(float(best_cost), 2),
            "savings": round(float(savings), 2),
            "savings_percent": round(float(percent), 4),
            "best_supplier_id": best["supplier_id"],
            "best_supplier_name": best["supplier_name"],
        }

    def get_price_history(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.history_repo.get_by_product(product_id, supplier_id, limit)]

    def get_price_changes(self, limit: int = 100):
        rows = self.history_repo.list_all(limit=limit)
        return [row.to_dict() for row in rows]
