from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException

from app.services.price_intelligence_service import PriceIntelligenceService

price_intelligence_bp = Blueprint("price_intelligence", __name__, url_prefix="/api/price-intelligence")


def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


@price_intelligence_bp.route("/products/<int:product_id>/comparison", methods=["GET"])
@login_required
def product_comparison(product_id):
    try:
        result = PriceIntelligenceService(current_user.tenant_id).compare_product(product_id)
        return jsonify({"success": True, **result})
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/products/<int:product_id>/savings", methods=["GET"])
@login_required
def product_savings(product_id):
    try:
        raw_quantity = request.args.get("quantity")
        if raw_quantity is None:
            raise BadRequest("quantity is required")
        try:
            quantity = float(raw_quantity)
        except (TypeError, ValueError):
            raise BadRequest("quantity must be a number")
        if quantity <= 0:
            raise BadRequest("quantity must be greater than zero")
        result = PriceIntelligenceService(current_user.tenant_id).calculate_savings(product_id, quantity)
        return jsonify({"success": True, **result})
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/products/<int:product_id>/history", methods=["GET"])
@login_required
def product_history(product_id):
    try:
        supplier_id = request.args.get("supplier_id", type=int)
        limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
        history = PriceIntelligenceService(current_user.tenant_id).get_price_history(product_id, supplier_id, limit)
        return jsonify({"success": True, "history": history})
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/changes", methods=["GET"])
@login_required
def price_changes():
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    changes = PriceIntelligenceService(current_user.tenant_id).get_price_changes(limit)
    return jsonify({"success": True, "changes": changes})


@price_intelligence_bp.route("/basket/analyze", methods=["POST"])
@login_required
def analyze_basket():
    try:
        payload = request.get_json(silent=True) or {}
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise BadRequest("items must be a non-empty array")
        max_suppliers = payload.get("max_suppliers")
        if max_suppliers is not None:
            try:
                max_suppliers = int(max_suppliers)
            except (TypeError, ValueError):
                raise BadRequest("max_suppliers must be an integer")
            if max_suppliers <= 0:
                raise BadRequest("max_suppliers must be greater than zero")
        result = PriceIntelligenceService(current_user.tenant_id).optimize_basket(items, max_suppliers)
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)
