from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.product import Product
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
        products = db.session.scalars(select(Product).where(Product.tenant_id == current_user.tenant_id, Product.active.is_(True)).order_by(Product.name.asc())).all()
        if search:
            products = [p for p in products if search in (p.name or "").casefold() or search in str(p.sku or "").casefold() or search in str(p.barcode or "").casefold()]
        intelligence = PriceIntelligenceService(current_user.tenant_id)
        rows = []
        for product in products[:limit]:
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
                "product_id": product.id, "product_name": product.name, "category": product.category,
                "sku": product.sku or product.supplier_sku, "barcode": product.barcode,
                "current_supplier": current.get("supplier_name") if current else None,
                "current_price": current_price, "currency": current.get("currency", "ILS") if current else (product.currency or "ILS"),
                "comparison_unit": current.get("comparison_unit") if current else (best.get("comparison_unit") if best else None),
                "best_supplier": best.get("supplier_name") if best else None, "best_price": best_price,
                "savings_per_unit": round(savings, 6), "savings_percent": round((savings / current_price * 100), 2) if current_price else 0.0,
                "supplier_count": len(all_offers),
                "offers": [{"supplier_id": row["supplier_id"], "supplier_name": row["supplier_name"], "price": row["normalized_price"], "currency": row["currency"], "unit": row.get("comparison_unit"), "primary": row.get("primary", False)} for row in all_offers],
            })
        rows.sort(key=lambda row: (-row["savings_per_unit"], row["product_name"]))
        summary = intelligence.get_portfolio_summary(opportunity_limit=10)
        supplier_scores = intelligence.get_supplier_price_scores(limit=10)
        return jsonify({"success": True, "summary": summary, "supplier_scores": supplier_scores, "products": rows, "returned": len(rows)})
    except (TypeError, ValueError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)
