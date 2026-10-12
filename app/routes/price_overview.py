from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.price_observation import PriceObservation
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.services.price_intelligence_service import PriceIntelligenceService

price_overview_bp = Blueprint("price_overview", __name__, url_prefix="/api/price-intelligence")


def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


@price_overview_bp.route("/overview", methods=["GET"])
@login_required
def overview():
    """Return a tenant-scoped supplier comparison without per-product query loops."""
    try:
        tenant_id = current_user.tenant_id
        limit = max(20, min(request.args.get("limit", default=150, type=int), 300))
        search = str(request.args.get("search") or "").strip()
        only_opportunities = str(request.args.get("opportunities") or "").lower() in {"1", "true", "yes"}

        primary_supplier = aliased(Supplier)
        alternate_supplier = aliased(Supplier)
        product_query = (
            select(Product)
            .outerjoin(
                primary_supplier,
                (primary_supplier.id == Product.supplier_id)
                & (primary_supplier.tenant_id == tenant_id),
            )
            .outerjoin(
                SupplierProductOffer,
                (SupplierProductOffer.product_id == Product.id)
                & (SupplierProductOffer.tenant_id == tenant_id),
            )
            .outerjoin(
                alternate_supplier,
                (alternate_supplier.id == SupplierProductOffer.supplier_id)
                & (alternate_supplier.tenant_id == tenant_id),
            )
            .where(Product.tenant_id == tenant_id, Product.active.is_(True))
            .distinct()
            .order_by(Product.name.asc(), Product.id.asc())
        )
        if search:
            pattern = f"%{search}%"
            product_query = product_query.where(or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.supplier_sku.ilike(pattern),
                Product.barcode.ilike(pattern),
                Product.category.ilike(pattern),
                primary_supplier.name.ilike(pattern),
                alternate_supplier.name.ilike(pattern),
            ))

        products = db.session.scalars(product_query.limit(limit)).all()
        if not products:
            return jsonify({
                "success": True,
                "summary": {
                    "products_analyzed": 0,
                    "products_with_comparable_alternatives": 0,
                    "opportunity_products": 0,
                    "current_unit_total": 0,
                    "best_unit_total": 0,
                    "potential_savings": 0,
                    "potential_savings_percent": 0,
                },
                "supplier_scores": {"products_analyzed": 0, "suppliers": []},
                "products": [],
                "returned": 0,
            })

        product_ids = [product.id for product in products]
        supplier_ids = {product.supplier_id for product in products}
        suppliers_by_id = {
            supplier.id: supplier
            for supplier in db.session.scalars(select(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.id.in_(supplier_ids),
            )).all()
        }

        offer_rows = db.session.execute(
            select(SupplierProductOffer, Supplier)
            .join(
                Supplier,
                (Supplier.id == SupplierProductOffer.supplier_id)
                & (Supplier.tenant_id == tenant_id)
                & (Supplier.active.is_(True)),
            )
            .where(
                SupplierProductOffer.tenant_id == tenant_id,
                SupplierProductOffer.product_id.in_(product_ids),
                SupplierProductOffer.active.is_(True),
                SupplierProductOffer.price > 0,
            )
            .order_by(SupplierProductOffer.product_id.asc(), SupplierProductOffer.price.asc())
        ).all()
        offers_by_product = {}
        for offer, supplier in offer_rows:
            payload = PriceIntelligenceService._price_payload(
                offer.supplier_id, supplier.name, offer.price, offer.unit,
                offer.units_per_carton, offer.currency,
            )
            offers_by_product.setdefault(offer.product_id, []).append(payload)

        observation_rows = db.session.execute(
            select(PriceObservation, Supplier)
            .join(
                Supplier,
                (Supplier.id == PriceObservation.supplier_id)
                & (Supplier.tenant_id == tenant_id)
                & (Supplier.active.is_(True)),
            )
            .where(
                PriceObservation.tenant_id == tenant_id,
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
        observations_by_product = {}
        seen_observations = set()
        for observation, supplier in observation_rows:
            key = (observation.product_id, observation.supplier_id)
            if key in seen_observations:
                continue
            seen_observations.add(key)
            unit = observation.unit or observation.comparison_unit
            cartons = observation.package_quantity if PriceIntelligenceService.normalize_unit(unit) == "CARTON" else None
            payload = PriceIntelligenceService._price_payload(
                observation.supplier_id, supplier.name, observation.observed_price,
                unit, cartons, observation.currency,
            )
            payload.update({
                "source_type": observation.source_type,
                "observed_at": observation.observed_at.isoformat() if observation.observed_at else None,
                "source_document_id": observation.source_document_id,
                "match_confidence": float(observation.match_confidence) if observation.match_confidence is not None else None,
            })
            observations_by_product.setdefault(observation.product_id, []).append(payload)

        rows = []
        for product in products:
            by_supplier = {}
            current = None
            if product.current_price is not None and float(product.current_price) > 0:
                supplier = suppliers_by_id.get(product.supplier_id)
                if supplier and supplier.active:
                    current = PriceIntelligenceService._price_payload(
                        product.supplier_id, supplier.name, product.current_price,
                        product.unit, product.units_per_carton, product.currency, primary=True,
                    )
                    by_supplier[product.supplier_id] = current

            for offer in offers_by_product.get(product.id, []):
                if offer["supplier_id"] not in by_supplier:
                    by_supplier[offer["supplier_id"]] = offer
            # Use the latest document price only when there is no active catalog
            # price for that supplier/product pair.
            for observation in observations_by_product.get(product.id, []):
                if observation["supplier_id"] not in by_supplier:
                    by_supplier[observation["supplier_id"]] = observation

            all_offers = list(by_supplier.values())
            if not all_offers:
                continue

            if current is not None:
                comparable = [
                    offer for offer in all_offers
                    if PriceIntelligenceService._incomparable_reason(current, offer) is None
                ]
            else:
                groups = {}
                for offer in all_offers:
                    unit = offer.get("comparison_unit")
                    if unit is not None:
                        groups.setdefault((offer["currency"], unit), []).append(offer)
                selected_group = min(
                    groups,
                    key=lambda key: (-len(groups[key]), key[0], key[1]),
                ) if groups else None
                comparable = groups.get(selected_group, []) if selected_group else []

            if current is not None and not comparable:
                comparable = [current]
            best = min(comparable, key=lambda offer: offer["normalized_price"]) if comparable else None
            current_price = current["normalized_price"] if current else None
            best_price = best["normalized_price"] if best else current_price
            savings = max(0.0, current_price - best_price) if current_price is not None and best_price is not None else 0.0
            if only_opportunities and savings <= 0:
                continue

            # Keep one offer per supplier and only within the selected comparable
            # currency/unit group. This prevents duplicated primary suppliers and
            # invalid comparisons across units or currencies.
            comparable_by_supplier = {}
            for offer in comparable:
                previous = comparable_by_supplier.get(offer["supplier_id"])
                if previous is None or offer["normalized_price"] < previous["normalized_price"]:
                    comparable_by_supplier[offer["supplier_id"]] = offer
            comparable = sorted(comparable_by_supplier.values(), key=lambda offer: (offer["normalized_price"], offer["supplier_name"] or ""))
            rows.append({
                "product_id": product.id,
                "product_name": product.name,
                "category": product.category,
                "sku": product.sku or product.supplier_sku,
                "barcode": product.barcode,
                "current_supplier": current.get("supplier_name") if current else None,
                "current_price": current_price,
                "currency": (current or best or {}).get("currency", product.currency or "ILS"),
                "comparison_unit": (current or best or {}).get("comparison_unit"),
                "best_supplier": best.get("supplier_name") if best else None,
                "best_supplier_id": best.get("supplier_id") if best else None,
                "best_price": best_price,
                "savings_per_unit": round(savings, 6),
                "savings_percent": round((savings / current_price * 100), 2) if current_price else 0.0,
                "supplier_count": len(comparable),
                "offers": [
                    {
                        "supplier_id": offer["supplier_id"],
                        "supplier_name": offer["supplier_name"],
                        "price": offer["normalized_price"],
                        "currency": offer["currency"],
                        "unit": offer.get("comparison_unit"),
                        "primary": offer.get("primary", False),
                    }
                    for offer in comparable
                ],
            })

        rows.sort(key=lambda row: (-row["savings_per_unit"], row["product_name"]))
        current_total = sum(row["current_price"] or 0 for row in rows)
        best_total = sum((row["best_price"] if row["best_price"] is not None else row["current_price"] or 0) for row in rows)
        potential_savings = max(0.0, current_total - best_total)
        comparable_count = sum(1 for row in rows if row["supplier_count"] >= 2)
        opportunities_count = sum(1 for row in rows if row["savings_per_unit"] > 0)

        supplier_stats = {}
        for row in rows:
            for offer in row["offers"]:
                entry = supplier_stats.setdefault(
                    offer["supplier_id"],
                    {"supplier_id": offer["supplier_id"], "supplier_name": offer["supplier_name"], "participation": 0, "wins": 0},
                )
                entry["participation"] += 1
                if row.get("best_supplier_id") == offer["supplier_id"] and row["best_price"] is not None and offer["price"] == row["best_price"]:
                    entry["wins"] += 1

        supplier_scores = []
        for entry in supplier_stats.values():
            coverage = entry["participation"] / comparable_count if comparable_count else 0
            win_rate = entry["wins"] / entry["participation"] if entry["participation"] else 0
            supplier_scores.append({
                **entry,
                "coverage_percent": round(coverage * 100, 1),
                "win_rate_percent": round(win_rate * 100, 1),
                "score": round((coverage * 50) + (win_rate * 50), 1),
            })
        supplier_scores.sort(key=lambda row: (-row["score"], -row["wins"], row["supplier_name"] or ""))

        summary = {
            "products_analyzed": len(rows),
            "products_with_comparable_alternatives": comparable_count,
            "opportunity_products": opportunities_count,
            "current_unit_total": round(current_total, 2),
            "best_unit_total": round(best_total, 2),
            "potential_savings": round(potential_savings, 2),
            "potential_savings_percent": round((potential_savings / current_total * 100), 2) if current_total else 0.0,
        }
        return jsonify({
            "success": True,
            "summary": summary,
            "supplier_scores": {"products_analyzed": comparable_count, "suppliers": supplier_scores[:10]},
            "products": rows,
            "returned": len(rows),
        })
    except (TypeError, ValueError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)
