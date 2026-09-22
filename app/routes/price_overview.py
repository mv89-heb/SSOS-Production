from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
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
    try:
        limit = max(20, min(request.args.get("limit", default=150, type=int), 300))
        search = str(request.args.get("search") or "").strip().casefold()
        only_opportunities = str(request.args.get("opportunities") or "").lower() in {"1", "true", "yes"}

        product_query = (
            select(Product)
            .outerjoin(Supplier, Supplier.id == Product.supplier_id)
            .outerjoin(SupplierProductOffer, SupplierProductOffer.product_id == Product.id)
            .where(
                Product.tenant_id == current_user.tenant_id,
                Product.active.is_(True),
            )
            .distinct()
            .order_by(Product.name.asc())
        )
        if search:
            pattern = f"%{search}%"
            product_query = product_query.where(
                or_(
                    Product.name.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.supplier_sku.ilike(pattern),
                    Product.barcode.ilike(pattern),
                    Product.category.ilike(pattern),
                    Supplier.name.ilike(pattern),
                )
            )

        products = db.session.scalars(product_query.limit(limit)).all()
        intelligence = PriceIntelligenceService(current_user.tenant_id)
        rows = []
        for product in products:
            comparison = intelligence.compare_product(product.id)
            current = comparison.get("current")
            best = comparison.get("best_offer")
            if not current and not comparison.get("offers"):
                continue

            all_offers = ([current] if current else []) + (comparison.get("offers") or [])
            prices = [float(row["normalized_price"]) for row in all_offers if row.get("normalized_price") is not None]
            best_price = float(best["normalized_price"]) if best else (min(prices) if prices else None)
            current_price = float(current["normalized_price"]) if current else None
            savings = max(0.0, current_price - best_price) if current_price is not None and best_price is not None else 0.0
            if only_opportunities and savings <= 0:
                continue

            rows.append({
                "product_id": product.id,
                "product_name": product.name,
                "category": product.category,
                "sku": product.sku or product.supplier_sku,
                "barcode": product.barcode,
                "current_supplier": current.get("supplier_name") if current else None,
                "current_price": current_price,
                "currency": current.get("currency", "ILS") if current else (product.currency or "ILS"),
                "comparison_unit": current.get("comparison_unit") if current else (best.get("comparison_unit") if best else None),
                "best_supplier": best.get("supplier_name") if best else None,
                "best_supplier_id": best.get("supplier_id") if best else None,
                "best_price": best_price,
                "savings_per_unit": round(savings, 6),
                "savings_percent": round((savings / current_price * 100), 2) if current_price else 0.0,
                "supplier_count": len(all_offers),
                "offers": [
                    {
                        "supplier_id": row["supplier_id"],
                        "supplier_name": row["supplier_name"],
                        "price": row["normalized_price"],
                        "currency": row["currency"],
                        "unit": row.get("comparison_unit"),
                        "primary": row.get("primary", False),
                    }
                    for row in all_offers
                ],
            })

        rows.sort(key=lambda row: (-row["savings_per_unit"], row["product_name"]))
        current_total = sum(row["current_price"] or 0 for row in rows)
        best_total = sum((row["best_price"] if row["best_price"] is not None else row["current_price"] or 0) for row in rows)
        potential_savings = max(0.0, current_total - best_total)
        comparable = sum(1 for row in rows if row["supplier_count"] >= 2)
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
        analyzed = comparable
        for entry in supplier_stats.values():
            coverage = entry["participation"] / analyzed if analyzed else 0
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
            "products_with_comparable_alternatives": comparable,
            "opportunity_products": opportunities_count,
            "current_unit_total": round(current_total, 2),
            "best_unit_total": round(best_total, 2),
            "potential_savings": round(potential_savings, 2),
            "potential_savings_percent": round((potential_savings / current_total * 100), 2) if current_total else 0.0,
        }
        return jsonify({
            "success": True,
            "summary": summary,
            "supplier_scores": {"products_analyzed": analyzed, "suppliers": supplier_scores[:10]},
            "products": rows,
            "returned": len(rows),
        })
    except (TypeError, ValueError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)
