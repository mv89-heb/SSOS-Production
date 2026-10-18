from collections import defaultdict
from decimal import Decimal, InvalidOperation
from itertools import combinations

from sqlalchemy import select

from app.extensions import db
from app.models.price_observation import PriceObservation
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
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
        "carton": "CARTON", "case": "CARTON", "קרטון": "CARTON", "קרטונים": "CARTON", "ארגז": "CARTON", "ארגזים": "CARTON",
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
            # A carton price is only comparable to a unit price when its
            # contents are known. Two cartons can contain different quantities.
            if cartons <= 0:
                return amount, None
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
        if left["comparison_unit"] is None or right["comparison_unit"] is None:
            return "חסרה יחידת השוואה — יש להשלים יחידת מכירה לפני דירוג"
        if left["comparison_unit"] != right["comparison_unit"]:
            return "יחידת השוואה שונה — לא ניתן להשוות מחיר ישירות"
        return None

    def _build_batch_comparison_context(self, products):
        """Load comparison data in a few tenant-scoped queries instead of N+1 lookups."""
        product_by_id = {product.id: product for product in products}
        product_ids = list(product_by_id)
        if not product_ids:
            return {"products": {}, "offers": {}, "observations": {}, "suppliers": {}}

        offers_by_product = defaultdict(list)
        offers = db.session.scalars(
            select(SupplierProductOffer)
            .where(
                SupplierProductOffer.tenant_id == self.tenant_id,
                SupplierProductOffer.product_id.in_(product_ids),
                SupplierProductOffer.active.is_(True),
            )
            .order_by(SupplierProductOffer.product_id.asc(), SupplierProductOffer.price.asc(), SupplierProductOffer.id.asc())
        ).all()
        for offer in offers:
            offers_by_product[offer.product_id].append(offer)

        # Only the latest positive observation per product/supplier is used as a
        # comparison source. Ordering lets Python select that row in one pass.
        observations_by_product = defaultdict(list)
        seen_observation_suppliers = set()
        observations = db.session.scalars(
            select(PriceObservation)
            .where(
                PriceObservation.tenant_id == self.tenant_id,
                PriceObservation.product_id.in_(product_ids),
                PriceObservation.observed_price > 0,
            )
            .order_by(
                PriceObservation.product_id.asc(),
                PriceObservation.supplier_id.asc(),
                PriceObservation.observed_at.desc(),
                PriceObservation.id.desc(),
            )
        ).all()
        for observation in observations:
            key = (observation.product_id, observation.supplier_id)
            if key in seen_observation_suppliers:
                continue
            seen_observation_suppliers.add(key)
            observations_by_product[observation.product_id].append(observation)

        supplier_ids = {
            product.supplier_id for product in products if product.supplier_id is not None
        }
        supplier_ids.update(offer.supplier_id for offer in offers if offer.supplier_id is not None)
        supplier_ids.update(row.supplier_id for row in observations if row.supplier_id is not None)
        suppliers = {}
        if supplier_ids:
            suppliers = {
                supplier.id: supplier
                for supplier in db.session.scalars(
                    select(Supplier).where(
                        Supplier.tenant_id == self.tenant_id,
                        Supplier.id.in_(supplier_ids),
                    )
                ).all()
            }
        return {
            "products": product_by_id,
            "offers": offers_by_product,
            "observations": observations_by_product,
            "suppliers": suppliers,
        }

    def _prepare_batch_comparison_context(self, products):
        # Keep lightweight test doubles and partial service objects on the
        # repository-backed path; production instances have all four repositories.
        if not all(hasattr(self, name) for name in (
            "tenant_id", "product_repo", "offer_repo", "observation_repo", "supplier_repo"
        )):
            self._comparison_context = None
            return
        self._comparison_context = self._build_batch_comparison_context(products)

    def compare_product(self, product_id: int):
        context = getattr(self, "_comparison_context", None)
        if context is not None and product_id in context["products"]:
            product = context["products"][product_id]
        else:
            product = self.product_repo.get_by_id_or_404(product_id)
        default_unit = self.normalize_unit(product.unit)
        by_supplier = {}

        def supplier_for(supplier_id):
            if context is not None:
                return context["suppliers"].get(supplier_id)
            return self.supplier_repo.get_by_id(supplier_id)

        if product.current_price is not None and self._decimal(product.current_price) > 0:
            primary_supplier = supplier_for(product.supplier_id)
            by_supplier[product.supplier_id] = self._price_payload(
                product.supplier_id,
                primary_supplier.name if primary_supplier else None,
                product.current_price,
                product.unit or default_unit,
                product.units_per_carton,
                product.currency,
                primary=True,
            )

        # Tenant-scoped offers are batch-loaded for portfolio endpoints; individual
        # product comparisons retain the same repository-backed fallback.
        if context is not None:
            product_offers = context["offers"].get(product_id, [])
        else:
            product_offers = self.offer_repo.get_by_product(product_id)
        for offer in product_offers:
            if not offer.active or self._decimal(offer.price) <= 0 or offer.supplier_id == product.supplier_id:
                continue
            supplier = supplier_for(offer.supplier_id)
            if supplier is None:
                continue
            by_supplier[offer.supplier_id] = self._price_payload(
                offer.supplier_id,
                supplier.name,
                offer.price,
                offer.unit,
                offer.units_per_carton,
                offer.currency,
            )

        # Invoice/delivery-document observations are also real supplier price
        # evidence. Portfolio endpoints batch-load the latest observations.
        if context is not None:
            observations = context["observations"].get(product_id, [])
        else:
            observation_repo = getattr(self, "observation_repo", None)
            observations = observation_repo.get_latest_by_product(product_id) if observation_repo is not None else []
        for observation in observations:
            if observation.supplier_id in by_supplier:
                continue
            supplier = supplier_for(observation.supplier_id)
            if supplier is None:
                continue
            unit = observation.unit or observation.comparison_unit or product.unit or default_unit
            units_per_carton = None
            if self.normalize_unit(unit) == "CARTON" and observation.package_quantity is not None:
                units_per_carton = observation.package_quantity
            row = self._price_payload(
                observation.supplier_id,
                supplier.name,
                observation.observed_price,
                unit,
                units_per_carton,
                observation.currency,
            )
            row["source_type"] = observation.source_type
            row["observed_at"] = observation.observed_at.isoformat() if observation.observed_at else None
            row["source_document_id"] = observation.source_document_id
            row["match_confidence"] = (
                float(observation.match_confidence) if observation.match_confidence is not None else None
            )
            by_supplier[observation.supplier_id] = row

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
        """Build a tenant-scoped executive snapshot without adding unlike currencies."""
        products = self.product_repo.get_all_for_matching()[:max(1, int(product_limit))]
        self._prepare_batch_comparison_context(products)
        totals_by_currency = {}
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
            currency = str(current.get("currency") or "ILS").upper()
            bucket = totals_by_currency.setdefault(currency, {
                "current_unit_total": Decimal("0"),
                "best_unit_total": Decimal("0"),
                "potential_savings": Decimal("0"),
                "opportunity_products": 0,
            })
            alternatives = [
                offer for offer in (comparison.get("offers") or [])
                if offer.get("supplier_id") != current.get("supplier_id")
            ]
            current_price = self._decimal(current["normalized_price"])
            best_price = current_price
            if alternatives:
                comparable_products += 1
                if best:
                    best_price = min(current_price, self._decimal(best["normalized_price"]))
            savings = max(Decimal("0"), current_price - best_price)
            bucket["current_unit_total"] += current_price
            bucket["best_unit_total"] += best_price
            bucket["potential_savings"] += savings
            if savings > 0:
                opportunity_count += 1
                bucket["opportunity_products"] += 1
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
                    "currency": currency,
                })
            analyzed.append(product)
        # Percentages can be ranked across currencies; absolute per-unit amounts cannot.
        opportunities.sort(key=lambda row: row["savings_percent"], reverse=True)
        currency_totals = {}
        for currency, bucket in totals_by_currency.items():
            current_total = bucket["current_unit_total"]
            best_total = bucket["best_unit_total"]
            potential = max(Decimal("0"), bucket["potential_savings"])
            percent = potential / current_total * Decimal("100") if current_total > 0 else Decimal("0")
            currency_totals[currency] = {
                "current_unit_total": round(float(current_total), 2),
                "best_unit_total": round(float(best_total), 2),
                "potential_savings": round(float(potential), 2),
                "potential_savings_percent": round(float(percent), 4),
                "opportunity_products": bucket["opportunity_products"],
            }

        # Legacy scalar fields are safe only for a single currency. When the
        # catalog contains multiple currencies, consumers must use currency_totals.
        if len(currency_totals) == 1:
            only_totals = next(iter(currency_totals.values()))
            current_unit_total = only_totals["current_unit_total"]
            best_unit_total = only_totals["best_unit_total"]
            potential_savings = only_totals["potential_savings"]
            potential_savings_percent = only_totals["potential_savings_percent"]
        elif not currency_totals:
            current_unit_total = best_unit_total = potential_savings = potential_savings_percent = 0
        else:
            current_unit_total = best_unit_total = potential_savings = potential_savings_percent = None

        result = {
            "products_analyzed": len(analyzed),
            "products_with_comparable_alternatives": comparable_products,
            "opportunity_products": opportunity_count,
            "currency_totals": currency_totals,
            "current_unit_total": current_unit_total,
            "best_unit_total": best_unit_total,
            "potential_savings": potential_savings,
            "potential_savings_percent": potential_savings_percent,
            "top_opportunities": opportunities[:max(1, int(opportunity_limit))],
            "recent_changes": [row.to_dict() for row in self.history_repo.list_all(limit=50)],
        }
        self._comparison_context = None
        return result

    def get_supplier_price_scores(self, product_limit: int = 2000, limit: int = 10):
        """Score suppliers on price competitiveness and coverage only; no invented quality metrics."""
        products = self.product_repo.get_all_for_matching()[:max(1, int(product_limit))]
        self._prepare_batch_comparison_context(products)
        stats = {}
        analyzed = 0
        for product in products:
            comparison = self.compare_product(product.id)
            current = comparison.get("current")
            if not current:
                continue
            alternatives = [
                offer for offer in (comparison.get("offers") or [])
                if offer.get("supplier_id") != current.get("supplier_id")
            ]
            candidates = [current] + alternatives
            if not alternatives:
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
        result = {"products_analyzed": analyzed, "suppliers": results[:max(1, int(limit))]}
        self._comparison_context = None
        return result

    def get_price_history(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.history_repo.get_by_product(product_id, supplier_id, limit)]

    def get_price_changes(self, limit: int = 100):
        return [row.to_dict() for row in self.history_repo.list_all(limit=limit)]

    def get_price_observations(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        self.product_repo.get_by_id_or_404(product_id)
        return [row.to_dict() for row in self.observation_repo.get_by_product(product_id, supplier_id, limit)]
