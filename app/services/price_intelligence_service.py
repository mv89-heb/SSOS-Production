from decimal import Decimal, InvalidOperation
from itertools import combinations

from app.extensions import db
from app.repositories.product_repository import ProductRepository
from app.repositories.price_history_repository import PriceHistoryRepository
from app.repositories.price_observation_repository import PriceObservationRepository
from app.models.price_history import PriceHistory


class PriceIntelligenceService:
    """Deterministic supplier-price comparison, observations, savings and baskets."""

    UNIT_ALIASES = {
        "unit": "UNIT", "units": "UNIT", "piece": "UNIT", "pieces": "UNIT",
        "יח": "UNIT", "יחידה": "UNIT", "יחידות": "UNIT", "פריט": "UNIT",
        "kg": "KG", "kgs": "KG", "קג": "KG", "ק"ג": "KG", "קילו": "KG", "קילוגרם": "KG",
        "g": "G", "גרם": "G",
        "liter": "L", "litre": "L", "l": "L", "ליטר": "L", "ליטרים": "L",
        "ml": "ML", "מיליליטר": "ML",
        "meter": "M", "מטר": "M",
        "pack": "PACK", "package": "PACK", "אריזה": "PACK", "מארז": "PACK",
        "carton": "CARTON", "case": "CARTON", "קרטון": "CARTON",
    }
    # Canonical comparison units are the units normally used for purchasing.
    # This keeps a quantity such as 5 KG compatible with a normalized price
    # expressed as price/KG rather than silently turning it into price/gram.
    UNIT_FACTORS = {
        "G": ("KG", Decimal("0.001")),
        "KG": ("KG", Decimal("1")),
        "ML": ("L", Decimal("0.001")),
        "L": ("L", Decimal("1")),
        "M": ("M", Decimal("1")),
        "UNIT": ("UNIT", Decimal("1")),
        "PACK": ("PACK", Decimal("1")),
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.product_repo = ProductRepository(tenant_id)
        self.history_repo = PriceHistoryRepository(tenant_id)
        self.observation_repo = PriceObservationRepository(tenant_id)

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
        if normalized == "CARTON":
            if cartons <= 0:
                return amount, "CARTON"
            amount = amount / cartons
            normalized = "UNIT"
        factor = cls.UNIT_FACTORS.get(normalized)
        if factor is None:
            return amount, normalized
        base_unit, source_to_base = factor
        # If one source unit is a fraction of the canonical unit, price per
        # canonical unit is price / source_to_base. Example: ₪0.50/g -> ₪500/kg.
        return amount / source_to_base, base_unit

    @classmethod
    def _price_payload(cls, supplier_id, supplier_name, price, unit, units_per_carton, currency, *, primary=False):
        normalized_price, comparison_unit = cls.normalize_offer_price(price, unit, units_per_carton)
        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "price": float(cls._decimal(price)),
            "currency": (currency or "ILS").upper(),
            "unit": unit,
            "comparison_unit": comparison_unit,
            "normalized_price": float(normalized_price),
            "primary": primary,
        }

    def compare_product(self, product_id: int):
        product = self.product_repo.get_by_id_or_404(product_id)
        default_unit = self.normalize_unit(product.unit) or "UNIT"
        by_supplier = {}
        if product.current_price is not None and self._decimal(product.current_price) > 0:
            by_supplier[product.supplier_id] = self._price_payload(
                product.supplier_id,
                product.supplier.name if product.supplier else None,
                product.current_price,
                product.unit or default_unit,
                product.units_per_carton,
                product.currency,
                primary=True,
            )
        for offer in product.supplier_offers:
            if not offer.active or self._decimal(offer.price) <= 0 or offer.supplier_id == product.supplier_id:
                continue
            by_supplier[offer.supplier_id] = self._price_payload(
                offer.supplier_id,
                offer.supplier.name if offer.supplier else None,
                offer.price,
                offer.unit or product.unit or default_unit,
                offer.units_per_carton,
                offer.currency,
            )
        offers = list(by_supplier.values())
        currencies = {row["currency"] for row in offers}
        comparable = []
        if len(currencies) == 1 and offers:
            units = {row["comparison_unit"] for row in offers}
            if len(units) == 1 and None not in units:
                comparable = offers
        comparable.sort(key=lambda row: row["normalized_price"])
        current = by_supplier.get(product.supplier_id)
        result = {
            "product": product.to_dict(), "current": current, "offers": comparable,
            "incomparable_offers": [row for row in offers if row not in comparable],
            "best_offer": comparable[0] if comparable else None,
            "saving_per_unit": 0.0, "saving_percent": 0.0,
        }
        best = result["best_offer"]
        if current and best and current["normalized_price"] > 0:
            saving = self._decimal(current["normalized_price"]) - self._decimal(best["normalized_price"])
            if saving > 0:
                result["saving_per_unit"] = round(float(saving), 6)
                result["saving_percent"] = round(float((saving / self._decimal(current["normalized_price"])) * 100), 4)
        return result

    def calculate_savings(self, product_id: int, quantity):
        comparison = self.compare_product(product_id)
        qty = self._decimal(quantity)
        current, best = comparison["current"], comparison["best_offer"]
        if qty <= 0 or not current or not best:
            return {"product_id": product_id, "quantity": float(qty), "current_cost": 0.0,
                    "best_cost": 0.0, "savings": 0.0, "savings_percent": 0.0,
                    "best_supplier_id": best["supplier_id"] if best else None}
        current_cost = self._decimal(current["normalized_price"]) * qty
        best_cost = self._decimal(best["normalized_price"]) * qty
        savings = max(Decimal("0"), current_cost - best_cost)
        percent = savings / current_cost * Decimal("100") if current_cost > 0 else Decimal("0")
        return {"product_id": product_id, "quantity": float(qty), "current_cost": round(float(current_cost), 2),
                "best_cost": round(float(best_cost), 2), "savings": round(float(savings), 2),
                "savings_percent": round(float(percent), 4), "best_supplier_id": best["supplier_id"],
                "best_supplier_name": best["supplier_name"]}

    def record_observation(self, *, product_id: int, supplier_id: int, observed_price, currency="ILS",
                           unit=None, package_quantity=None, comparison_unit=None, price_basis="NET",
                           source_type="INVOICE", source_document_id=None, match_method=None,
                           match_confidence=None, observed_at=None):
        """Persist a source observation without changing catalog prices."""
        self.product_repo.get_by_id_or_404(product_id)
        amount = self._decimal(observed_price)
        if amount <= 0:
            raise ValueError("observed_price must be greater than zero")
        _, inferred_unit = self.normalize_offer_price(amount, unit, package_quantity)
        row = self.observation_repo.create(
            product_id=product_id, supplier_id=supplier_id, source_document_id=source_document_id,
            observed_price=amount, currency=(currency or "ILS").upper(), unit=unit,
            package_quantity=package_quantity, comparison_unit=comparison_unit or inferred_unit,
            price_basis=price_basis or "NET", source_type=source_type or "INVOICE",
            match_method=match_method, match_confidence=match_confidence, observed_at=observed_at,
        )
        db.session.flush()
        return row

    def accept_price_change(self, *, product_id: int, supplier_id: int, new_price, currency="ILS", unit=None,
                            source_type="MANUAL", source_document_id=None, effective_at=None):
        """Record an accepted price change; catalog mutation stays in the caller's transaction."""
        product = self.product_repo.get_by_id_or_404(product_id)
        amount = self._decimal(new_price)
        if amount <= 0:
            raise ValueError("new_price must be greater than zero")
        if supplier_id == product.supplier_id:
            old = self._decimal(product.current_price)
        else:
            offer = next((o for o in product.supplier_offers if o.supplier_id == supplier_id), None)
            if offer is None:
                raise ValueError("Supplier does not have an offer for this product")
            old = self._decimal(offer.price)
        change_percent = (amount - old) / old * Decimal("100") if old > 0 else None
        history = PriceHistory(
            tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id,
            old_price=old if old > 0 else None, new_price=amount,
            currency=(currency or "ILS").upper(), unit=unit, source_type=source_type,
            source_document_id=source_document_id, effective_at=effective_at,
            change_percent=change_percent,
        )
        db.session.add(history)
        db.session.flush()
        return history

    def optimize_basket(self, items: list[dict], max_suppliers: int | None = None):
        """Find the cheapest comparable basket before shipping/minimum-order constraints."""
        normalized_items, supplier_pool = [], {}
        current_total = Decimal("0")
        for raw in items:
            product_id, quantity = raw.get("product_id"), self._decimal(raw.get("quantity"))
            if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0 or quantity <= 0:
                raise ValueError("Each basket item requires a positive product_id and quantity")
            comparison = self.compare_product(product_id)
            if not comparison["current"] or not comparison["offers"]:
                raise ValueError(f"Product {product_id} has no comparable supplier prices")
            current_total += self._decimal(comparison["current"]["normalized_price"]) * quantity
            normalized_items.append((product_id, quantity, comparison))
            for offer in comparison["offers"]:
                supplier_pool[offer["supplier_id"]] = offer["supplier_name"]

        def evaluate(allowed_suppliers=None):
            assignments, total = [], Decimal("0")
            for product_id, quantity, comparison in normalized_items:
                offers = comparison["offers"] if allowed_suppliers is None else [
                    o for o in comparison["offers"] if o["supplier_id"] in allowed_suppliers
                ]
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
        return {"current_cost": round(float(current_total), 2), "optimized_cost": round(float(optimized_total), 2),
                "savings": round(float(savings), 2), "savings_percent": round(float(percent), 4),
                "supplier_count": len(grouped), "suppliers": list(grouped.values())}

    def get_price_history(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.history_repo.get_by_product(product_id, supplier_id, limit)]

    def get_price_changes(self, limit: int = 100):
        return [row.to_dict() for row in self.history_repo.list_all(limit=limit)]

    def get_price_observations(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.observation_repo.get_by_product(product_id, supplier_id, limit)]
