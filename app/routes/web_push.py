from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest

from app.services.web_push_service import public_key, remove_subscription, save_subscription

web_push_bp = Blueprint("web_push", __name__, url_prefix="/api/push")


@web_push_bp.route("/public-key", methods=["GET"])
def get_public_key():
    return jsonify({"success": True, "public_key": public_key()})


@web_push_bp.route("/subscribe", methods=["POST"])
@login_required
def subscribe():
    payload = request.get_json(silent=True) or {}
    try:
        subscription = save_subscription(
            current_user.id,
            current_user.tenant_id,
            payload,
            request.headers.get("User-Agent"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": "invalid_subscription", "message": str(exc)}), 400
    return jsonify({"success": True, "subscription": subscription.to_dict()})


@web_push_bp.route("/unsubscribe", methods=["POST"])
@login_required
def unsubscribe():
    payload = request.get_json(silent=True) or {}
    endpoint = str(payload.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"success": False, "error": "endpoint_required"}), 400
    remove_subscription(current_user.id, endpoint)
    return jsonify({"success": True})
