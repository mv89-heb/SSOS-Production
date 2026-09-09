from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, ServiceUnavailable

from app.services.ai_service import AIService
from app.services.data_readiness_service import ProcurementDataReadinessService
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


@price_intelligence_bp.route("/products/<int:product_id>/observations", methods=["GET"])
@login_required
def product_observations(product_id):
    try:
        supplier_id = request.args.get("supplier_id", type=int)
        limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
        observations = PriceIntelligenceService(current_user.tenant_id).get_price_observations(product_id, supplier_id, limit)
        return jsonify({"success": True, "observations": observations})
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/changes", methods=["GET"])
@login_required
def price_changes():
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    changes = PriceIntelligenceService(current_user.tenant_id).get_price_changes(limit)
    return jsonify({"success": True, "changes": changes})


@price_intelligence_bp.route("/summary", methods=["GET"])
@login_required
def portfolio_summary():
    """Return a deterministic tenant-scoped procurement snapshot for the dashboard."""
    try:
        limit = max(1, min(request.args.get("limit", default=10, type=int), 50))
        result = PriceIntelligenceService(current_user.tenant_id).get_portfolio_summary(opportunity_limit=limit)
        return jsonify({"success": True, **result})
    except (TypeError, ValueError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/supplier-scores", methods=["GET"])
@login_required
def supplier_price_scores():
    """Rank suppliers by price competitiveness and catalog coverage only."""
    try:
        limit = max(1, min(request.args.get("limit", default=10, type=int), 50))
        result = PriceIntelligenceService(current_user.tenant_id).get_supplier_price_scores(limit=limit)
        return jsonify({"success": True, **result})
    except (TypeError, ValueError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)


@price_intelligence_bp.route("/data-readiness", methods=["GET"])
@login_required
def procurement_data_readiness():
    """Return factual data coverage so the UI can distinguish empty intelligence from missing source data."""
    result = ProcurementDataReadinessService(current_user.tenant_id).snapshot()
    return jsonify({"success": True, **result})


def _build_briefing_prompt(summary: dict, supplier_scores: dict) -> str:
    return (
        "You are the executive procurement briefing layer inside SSOS. Analyze ONLY the supplied deterministic facts. "
        "Do not invent market prices, supplier quality, delivery times, stock, contracts, or savings beyond the supplied numbers. "
        "Return valid JSON only with keys: headline, highlights, risks, actions. "
        "All values must be concise Hebrew strings; arrays must contain short actionable strings.\n\n"
        f"PORTFOLIO SUMMARY: {summary}\n"
        f"SUPPLIER PRICE SCORES: {supplier_scores}\n"
    )


@price_intelligence_bp.route("/ai-briefing", methods=["POST"])
@login_required
def portfolio_ai_briefing():
    """Generate a read-only Gemini executive briefing from deterministic portfolio facts."""
    try:
        intelligence = PriceIntelligenceService(current_user.tenant_id)
        summary = intelligence.get_portfolio_summary(opportunity_limit=10)
        supplier_scores = intelligence.get_supplier_price_scores(limit=10)
        ai = AIService.from_config(current_app.config)
        if not ai.is_available():
            raise ServiceUnavailable("Gemini is not configured for this environment")
        result = ai.generate_text(_build_briefing_prompt(summary, supplier_scores))
        if not result.success:
            raise ServiceUnavailable("Gemini could not generate the briefing right now")
        import json
        try:
            briefing = json.loads(result.text or "{}")
        except json.JSONDecodeError:
            raise ServiceUnavailable("Gemini returned an invalid briefing")
        if not isinstance(briefing, dict):
            raise ServiceUnavailable("Gemini returned an invalid briefing")
        return jsonify({
            "success": True,
            "provider": result.provider,
            "model": result.model,
            "briefing": {
                "headline": str(briefing.get("headline") or "אין סיכום זמין כרגע"),
                "highlights": briefing.get("highlights") if isinstance(briefing.get("highlights"), list) else [],
                "risks": briefing.get("risks") if isinstance(briefing.get("risks"), list) else [],
                "actions": briefing.get("actions") if isinstance(briefing.get("actions"), list) else [],
            },
        })
    except ServiceUnavailable as exc:
        return _handle(exc)
    except HTTPException as exc:
        return _handle(exc)


def _build_gemini_prompt(comparison: dict, history: list[dict], quantity: float) -> str:
    product = comparison.get("product") or {}
    current = comparison.get("current")
    offers = comparison.get("offers") or []
    incomparable = comparison.get("incomparable_offers") or []
    compact_history = history[:20]
    return (
        "You are the procurement decision-support layer inside SSOS. Analyze ONLY the supplied facts. "
        "Do not invent supplier capabilities, delivery times, stock, MOQ, contracts, or market prices. "
        "Deterministic price calculations are authoritative; you explain and prioritize them. "
        "Return valid JSON only with keys: recommendation, confidence, reasons, risks, trend, actions. "
        "recommendation must be the supplier name or null. confidence is 0-100. reasons, risks and actions are arrays of short Hebrew strings. "
        "trend is a short Hebrew string. If evidence is insufficient, say so explicitly.\n\n"
        f"PRODUCT: {product.get('name')} | SKU: {product.get('sku')} | quantity={quantity}\n"
        f"CURRENT: {current}\n"
        f"COMPARABLE OFFERS: {offers}\n"
        f"INCOMPARABLE OFFERS: {incomparable}\n"
        f"PRICE HISTORY: {compact_history}\n"
        f"DETERMINISTIC SAVINGS: per_unit={comparison.get('saving_per_unit')} percent={comparison.get('saving_percent')}\n"
    )


@price_intelligence_bp.route("/products/<int:product_id>/ai-insight", methods=["POST"])
@login_required
def product_ai_insight(product_id):
    """Ask Gemini to explain the deterministic supplier comparison without changing data."""
    try:
        payload = request.get_json(silent=True) or {}
        raw_quantity = payload.get("quantity", 100)
        try:
            quantity = float(raw_quantity)
        except (TypeError, ValueError):
            raise BadRequest("quantity must be a number")
        if quantity <= 0:
            raise BadRequest("quantity must be greater than zero")

        intelligence = PriceIntelligenceService(current_user.tenant_id)
        comparison = intelligence.compare_product(product_id)
        history = intelligence.get_price_history(product_id, limit=20)
        ai = AIService.from_config(current_app.config)
        if not ai.is_available():
            raise ServiceUnavailable("Gemini is not configured for this environment")

        result = ai.generate_text(_build_gemini_prompt(comparison, history, quantity))
        if not result.success:
            raise ServiceUnavailable("Gemini could not analyze the comparison right now")

        import json
        try:
            insight = json.loads(result.text or "{}")
        except json.JSONDecodeError:
            raise ServiceUnavailable("Gemini returned an invalid analysis")
        if not isinstance(insight, dict):
            raise ServiceUnavailable("Gemini returned an invalid analysis")

        return jsonify({
            "success": True,
            "provider": result.provider,
            "model": result.model,
            "insight": {
                "recommendation": insight.get("recommendation"),
                "confidence": max(0, min(100, int(insight.get("confidence") or 0))),
                "reasons": insight.get("reasons") if isinstance(insight.get("reasons"), list) else [],
                "risks": insight.get("risks") if isinstance(insight.get("risks"), list) else [],
                "trend": str(insight.get("trend") or "אין מספיק נתונים לקביעת מגמה"),
                "actions": insight.get("actions") if isinstance(insight.get("actions"), list) else [],
            },
        })
    except (BadRequest, ServiceUnavailable) as exc:
        return _handle(exc)
    except HTTPException as exc:
        return _handle(exc)


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
