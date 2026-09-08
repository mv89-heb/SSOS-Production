from decimal import Decimal, InvalidOperation
from itertools import combinations

from app.extensions import db
from app.repositories.product_repository import ProductRepository
from app.repositories.price_history_repository import PriceHistoryRepository
from app.repositories.price_observation_repository import PriceObservationRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_offer_repository import SupplierOfferRepository
from app.models.price_history import PriceHistory


class PriceIntelligenceService:
    """Deterministic supplier-price comparison, observations, savings and baskets."""

    UNIT_ALIASES = {
        "unit": "UNIT", "units": "UNIT", "piece": "UNIT", "pieces": "UNIT",
        "יח": "UNIT", "יחידה": "UNIT", "יחידות": "UNIT", "פריט": "UNIT",
        "kg": "KG", "kgs": "KG", "קג": "KG", 'ק"ג': "KG", "קילו": "KG", "קילוגרם": "KG",
        "g": "G", "גרם": "G",
        "liter": "L", "litre": "L", "l": "L", "ליטר": "L", "ליטרים": "L",
        "ml": "ML", "מיליליטר": "ML",
        "meter": "M", "מטר": "M",
        "pack": "PACK", "package": "PACK", "אריזה": "PACK", "מארז": "PACK",
        "carton": "CARTON", "case": "CARTON", "קרטון": "CARTON",
    }
    UNIT_FACTORS = {
        "G": ("KG", Decimal("0.001")), "KG": ("KG", Decimal("1")),
        "ML": ("L", Decimal("0.001")), "L": ("L", Decimal("1")),
        "M": ("M", Decimal("1")), "UNIT": ("UNIT", Decimal("1")),
        "PACK": ("PACK", Decimal("1")), "CARTON": ("CARTON", Decimal("1")),
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.product_repo = ProductRepository(tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id)
        self.offer_repo = SupplierOfferRepository(tenant_id)
        self.history_repo = PriceHistoryRepository(tenant_id)
        self.observation_repo = PriceObservationRepository(tenant_id)

    @staticmethod
    def _decimal(value) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid decimal value")

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
        cartons = cls._decimal(units_per_carton) if units_per_carton is not None else Decimal("0")
        if normalized == "CARTON":
            if cartons <= 0:
                return amount, "CARTON"
            amount = amount / cartons
            normalized = "UNIT"
        factor = cls.UNIT_FACTORS.get(normalized)
        if factor is None:
            return amount, normalized
        base_unit, source_to_base = factor
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

    @staticmethod
    def _incomparable_reason(left, right) -> str | None:
        if left["currency"] != right["currency"]:
            return "מטבע שונה — נדרש שער המרה לפני השוואה"
        if left["comparison_unit"] != right["comparison_unit"]:
            return "יחידת השוואה שונה — לא ניתן להשוות מחיר ישירות"
        if left["comparison_unit"] is None:
            return "חסרה יחידת השוואה"
        return None

    def compare_product(self, product_id: int):
        product = self.product_repo.get_by_id_or_404(product_id)
        default_unit = self.normalize_unit(product.unit) or "UNIT"
        by_supplier = {}

        if product.current_price is not None and self._decimal(product.current_price) > 0:
            primary_supplier = self.supplier_repo.get_by_id(product.supplier_id)
            by_supplier[product.supplier_id] = self._price_payload(
                product.supplier_id,
                primary_supplier.name if primary_supplier else None,
                product.current_price,
                product.unit or default_unit,
                product.units_per_carton,
                product.currency,
                primary=True,
            )

        # Product.supplier_offers is not tenant-filtered at relationship level.
        # Read through the tenant-scoped repository so malformed cross-tenant rows
        # can never leak into the comparison result.
        for offer in self.offer_repo.get_by_product(product_id):
            if not offer.active or self._decimal(offer.price) <= 0 or offer.supplier_id == product.supplier_id:
                continue
            supplier = self.supplier_repo.get_by_id(offer.supplier_id)
            if supplier is None:
                continue
            by_supplier[offer.supplier_id] = self._price_payload(
                offer.supplier_id,
                supplier.name,
                offer.price,
                offer.unit or product.unit or default_unit,
                offer.units_per_carton,
                offer.currency,
            )

        offers = list(by_supplier.values())
        current = by_supplier.get(product.supplier_id)
        comparable = []
        incomparable = []

        if current is not None:
            for row in offers:
                reason = self._incomparable_reason(current, row)
                if reason is None:
                    comparable.append(row)
                else:
                    incomparable.append({**row, "incomparable_reason": reason})
        elif offers:
            # In an incomplete catalog there may be no current price. Still compare
            # alternate offers against each other so the screen remains useful.
            anchor = offers[0]
            for row in offers:
                reason = self._incomparable_reason(anchor, row)
                if reason is None:
                    comparable.append(row)
                else:
                    incomparable.append({**row, "incomparable_reason": reason})

        comparable.sort(key=lambda row: row["normalized_price"])
        result = {
            "product": product.to_dict(),
            "current": current,
            "offers": comparable,
            "incomparable_offers": incomparable,
            "best_offer": comparable[0] if comparable else None,
            "saving_per_unit": 0.0,
            "saving_percent": 0.0,
        }
        best = result["best_offer"]
        if current and best and current["normalized_price"] > 0:
            saving = self._decimal(current["normalized_price"]) - self._decimal(best["normalized_price"])
            if saving > 0:
                result["saving_per_unit"] = round(float(saving), 6)
                result["saving_percent"] = round(float(saving / self._decimal(current["normalized_price"]) * 100), 4)
        return result

    def calculate_savings(self, product_id: int, quantity):
        comparison = self.compare_product(product_id)
        qty = self._decimal(quantity)
        current, best = comparison["current"], comparison["best_offer"]
        if qty <= 0 or not current or not best:
            return {
                "product_id": product_id,
                "quantity": float(qty),
                "current_cost": 0.0,
                "best_cost": 0.0,
                "savings": 0.0,
                "savings_percent": 0.0,
                "best_supplier_id": best["supplier_id"] if best else None,
                "best_supplier_name": best["supplier_name"] if best else None,
            }
        current_cost = self._decimal(current["normalized_price"]) * qty
        best_cost = self._decimal(best["normalized_price"]) * qty
        savings = max(Decimal("0"), current_cost - best_cost)
        percent = savings / current_cost * Decimal("100") if current_cost > 0 else Decimal("0")
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

    def record_observation(self, *, product_id: int, supplier_id: int, observed_price, currency="ILS",
                           unit=None, package_quantity=None, comparison_unit=None, price_basis="NET",
                           source_type="INVOICE", source_document_id=None, match_method=None,
                           match_confidence=None, observed_at=None):
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
                offers = comparison["offers"] if allowed_suppliers is None else [o for o in comparison["offers"] if o["supplier_id"] in allowed_suppliers]
                if not offers:
                    return None
                offer = min(offers, key=lambda row: row["normalized_price"])
                line_total = self._decimal(offer["normalized_price"]) * quantity
                total += line_total
                assignments.append({"product_id": product_id, "quantity": float(quantity), "supplier_id": offer["supplier_id"],
                                    "supplier_name": offer["supplier_name"], "unit_price": offer["normalized_price"],
                                    "line_total": round(float(line_total), 2)})
            return total, assignments

        best_result = evaluate()
        if max_suppliers is not None:
            try:
                max_suppliers = int(max_suppliers)
            except (TypeError, ValueError):
                raise ValueError("max_suppliers must be an integer")
            if max_suppliers < 1:
                raise ValueError("max_suppliers must be at least 1")
            max_suppliers = min(max_suppliers, len(supplier_pool))
            candidates = list(supplier_pool)
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

    def get_portfolio_summary(self, product_limit: int = 2000, opportunity_limit: int = 10):
        """Build a tenant-scoped executive snapshot from deterministic price facts."""
        products = self.product_repo.get_all_for_matching()[:max(1, int(product_limit))]
        total_current = Decimal("0")
        total_best = Decimal("0")
        opportunity_count = 0
        comparable_products = 0
        opportunities = []
        analyzed = []
        for product in products:
            try:
                comparison = self.compare_product(product.id)
            except (ValueError, TypeError):
                continue
            current = comparison.get("current")
            best = comparison.get("best_offer")
            if not current:
                continue
            current_price = self._decimal(current["normalized_price"])
            total_current += current_price
            best_price = current_price
            if best and comparison.get("offers"):
                comparable_products += 1
                best_price = min(current_price, self._decimal(best["normalized_price"]))
            total_best += best_price
            savings = max(Decimal("0"), current_price - best_price)
            if savings > 0:
                opportunity_count += 1
                opportunities.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "current_supplier": current.get("supplier_name"),
                    "best_supplier": best.get("supplier_name") if best else None,
                    "current_price": float(current_price),
                    "best_price": float(best_price),
                    "savings_per_unit": round(float(savings), 6),
                    "savings_percent": round(float(savings / current_price * Decimal("100")), 4) if current_price else 0.0,
                    "currency": current.get("currency", "ILS"),
                })
            analyzed.append(product)
        opportunities.sort(key=lambda row: row["savings_per_unit"], reverse=True)
        potential_savings = max(Decimal("0"), total_current - total_best)
        savings_percent = potential_savings / total_current * Decimal("100") if total_current > 0 else Decimal("0")
        return {
            "products_analyzed": len(analyzed),
            "products_with_comparable_alternatives": comparable_products,
            "opportunity_products": opportunity_count,
            "current_unit_total": round(float(total_current), 2),
            "best_unit_total": round(float(total_best), 2),
            "potential_savings": round(float(potential_savings), 2),
            "potential_savings_percent": round(float(savings_percent), 4),
            "top_opportunities": opportunities[:max(1, int(opportunity_limit))],
            "recent_changes": [row.to_dict() for row in self.history_repo.list_all(limit=10)],
        }

    def get_supplier_price_scores(self, product_limit: int = 2000, limit: int = 10):
        """Score suppliers on price competitiveness and coverage only; no invented quality metrics."""
        products = self.product_repo.get_all_for_matching()[:max(1, int(product_limit))]
        stats = {}
        analyzed = 0
        for product in products:
            comparison = self.compare_product(product.id)
            current = comparison.get("current")
            if not current:
                continue
            candidates = [current] + list(comparison.get("offers") or [])
            if len(candidates) < 2:
                continue
            analyzed += 1
            cheapest = min(candidates, key=lambda row: row["normalized_price"])
            for row in candidates:
                supplier_id = row["supplier_id"]
                entry = stats.setdefault(supplier_id, {"supplier_id": supplier_id, "supplier_name": row.get("supplier_name"), "participation": 0, "wins": 0})
                entry["participation"] += 1
                if supplier_id == cheapest["supplier_id"]:
                    entry["wins"] += 1
        results = []
        for entry in stats.values():
            coverage = entry["participation"] / analyzed if analyzed else 0
            win_rate = entry["wins"] / entry["participation"] if entry["participation"] else 0
            score = round((coverage * 50) + (win_rate * 50), 1)
            results.append({**entry, "coverage_percent": round(coverage * 100, 1), "win_rate_percent": round(win_rate * 100, 1), "score": score})
        results.sort(key=lambda row: (-row["score"], -row["wins"], row["supplier_name"] or ""))
        return {"products_analyzed": analyzed, "suppliers": results[:max(1, int(limit))]}

    def get_price_history(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.history_repo.get_by_product(product_id, supplier_id, limit)]

    def get_price_changes(self, limit: int = 100):
        return [row.to_dict() for row in self.history_repo.list_all(limit=limit)]

    def get_price_observations(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.observation_repo.get_by_product(product_id, supplier_id, limit)]
