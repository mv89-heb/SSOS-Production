from decimal import Decimal, InvalidOperation
from itertools import combinations

from app.repositories.product_repository import ProductRepository
from app.repositories.price_history_repository import PriceHistoryRepository


class PriceIntelligenceService:
    """Deterministic supplier-price comparison, savings, and basket optimization."""

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
                product.supplier_id, product.supplier.name if product.supplier else None,
                product.current_price, product.unit or default_unit, product.units_per_carton,
                product.currency, primary=True,
            ))

        for offer in product.supplier_offers:
            if not offer.active or self._decimal(offer.price) <= 0:
                continue
            offers.append(self._price_payload(
                offer.supplier_id, offer.supplier.name if offer.supplier else None,
                offer.price, offer.unit or product.unit or default_unit,
                offer.units_per_carton, offer.currency,
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
            "product": product.to_dict(), "current": current, "offers": comparable,
            "incomparable_offers": [row for row in offers if row not in comparable],
            "best_offer": best, "saving_per_unit": 0.0, "saving_percent": 0.0,
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
            return {"product_id": product_id, "quantity": float(qty), "current_cost": 0.0,
                    "best_cost": 0.0, "savings": 0.0, "savings_percent": 0.0,
                    "best_supplier_id": best["supplier_id"] if best else None}
        current_cost = self._decimal(current["normalized_price"]) * qty
        best_cost = self._decimal(best["normalized_price"]) * qty
        savings = max(Decimal("0"), current_cost - best_cost)
        percent = (savings / current_cost * Decimal("100")) if current_cost > 0 else Decimal("0")
        return {"product_id": product_id, "quantity": float(qty), "current_cost": round(float(current_cost), 2),
                "best_cost": round(float(best_cost), 2), "savings": round(float(savings), 2),
                "savings_percent": round(float(percent), 4), "best_supplier_id": best["supplier_id"],
                "best_supplier_name": best["supplier_name"]}

    def optimize_basket(self, items: list[dict], max_suppliers: int | None = None):
        """Find the cheapest comparable basket before shipping/minimum-order constraints.

        With no supplier-count limit, each line goes to its cheapest supplier.
        With a limit, the service evaluates supplier subsets, which makes the
        result exact for the candidate supplier set while remaining bounded.
        """
        normalized_items = []
        supplier_pool = {}
        current_total = Decimal("0")
        for raw in items:
            product_id = raw.get("product_id")
            quantity = self._decimal(raw.get("quantity"))
            if not isinstance(product_id, int) or product_id <= 0 or quantity <= 0:
                raise ValueError("Each basket item requires a positive product_id and quantity")
            comparison = self.compare_product(product_id)
            if not comparison["current"] or not comparison["offers"]:
                raise ValueError(f"Product {product_id} has no comparable supplier prices")
            current_total += self._decimal(comparison["current"]["normalized_price"]) * quantity
            normalized_items.append((product_id, quantity, comparison))
            for offer in comparison["offers"]:
                supplier_pool[offer["supplier_id"]] = offer["supplier_name"]

        def evaluate(allowed_suppliers=None):
            assignments = []
            total = Decimal("0")
            for product_id, quantity, comparison in normalized_items:
                offers = comparison["offers"]
                if allowed_suppliers is not None:
                    offers = [o for o in offers if o["supplier_id"] in allowed_suppliers]
                if not offers:
                    return None
                offer = min(offers, key=lambda row: row["normalized_price"])
                line_total = self._decimal(offer["normalized_price"]) * quantity
                total += line_total
                assignments.append({"product_id": product_id, "quantity": float(quantity),
                                    "supplier_id": offer["supplier_id"], "supplier_name": offer["supplier_name"],
                                    "unit_price": offer["normalized_price"], "line_total": round(float(line_total), 2)})
            return total, assignments

        best_result = evaluate()
        if max_suppliers is not None:
            max_suppliers = max(1, min(int(max_suppliers), len(supplier_pool)))
            candidates = list(supplier_pool)[:12]
            best_result = None
            for size in range(1, max_suppliers + 1):
                for subset in combinations(candidates, size):
                    result = evaluate(set(subset))
                    if result and (best_result is None or result[0] < best_result[0]):
                        best_result = result

        if best_result is None:
            raise ValueError("No feasible supplier combination for this basket")
        optimized_total, assignments = best_result
        grouped = {}
        for row in assignments:
            grouped.setdefault(row["supplier_id"], {"supplier_id": row["supplier_id"], "supplier_name": row["supplier_name"], "items": []})["items"].append(row)
        savings = max(Decimal("0"), current_total - optimized_total)
        percent = savings / current_total * Decimal("100") if current_total > 0 else Decimal("0")
        return {
            "current_cost": round(float(current_total), 2),
            "optimized_cost": round(float(optimized_total), 2),
            "savings": round(float(savings), 2),
            "savings_percent": round(float(percent), 4),
            "supplier_count": len(grouped),
            "suppliers": list(grouped.values()),
        }

    def get_price_history(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.history_repo.get_by_product(product_id, supplier_id, limit)]

    def get_price_changes(self, limit: int = 100):
        return [row.to_dict() for row in self.history_repo.list_all(limit=limit)]
