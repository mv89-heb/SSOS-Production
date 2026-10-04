from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, ServiceUnavailable
from app.repositories.product_repository import ProductRepository
from app.services.gemini_price_completion_service import GeminiPriceCompletionError, GeminiPriceCompletionService
from app.services.permission_service import PermissionService

gemini_price_completion_bp = Blueprint("gemini_price_completion", __name__, url_prefix="/api/price-intelligence")

def _handle(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code

@gemini_price_completion_bp.route("/price-completion/status", methods=["GET"])
@login_required
def status():
    products = ProductRepository(current_user.tenant_id).get_all_for_matching()
    active = [p for p in products if p.active]
    missing = [p for p in active if p.current_price is None or float(p.current_price or 0) <= 0]
    return jsonify({"success": True, "total_active": len(active), "missing_price": len(missing), "priced": len(active) - len(missing), "missing_product_ids": [p.id for p in missing]})

@gemini_price_completion_bp.route("/price-completion/run", methods=["POST"])
@login_required
def run():
    try:
        PermissionService.require_role_at_least("manager")
        payload = request.get_json(silent=True) or {}
        batch_size = int(payload.get("batch_size", 5))
        if not 1 <= batch_size <= 10:
            raise BadRequest("batch_size must be between 1 and 10")
        raw_ids = payload.get("product_ids", [])
        if not isinstance(raw_ids, list) or len(raw_ids) > 10:
            raise BadRequest("product_ids must be an array with at most 10 items")
        product_ids = [int(pid) for pid in raw_ids]
        if not current_app.config.get("GEMINI_ENABLED") or not current_app.config.get("GEMINI_API_KEY"):
            raise ServiceUnavailable("Gemini אינו מוגדר בסביבה הזו")
        result = GeminiPriceCompletionService(current_user.tenant_id, current_user.id, current_app.config).run_batch(batch_size, product_ids)
        return jsonify({"success": True, **result})
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "bad_request", "message": "batch_size/product_ids אינם תקינים"}), 400
    except (BadRequest, ServiceUnavailable) as exc:
        return _handle(exc)
    except GeminiPriceCompletionError as exc:
        return jsonify({"success": False, "error": "gemini_price_completion_failed", "message": str(exc)}), 422
    except HTTPException as exc:
        return _handle(exc)
