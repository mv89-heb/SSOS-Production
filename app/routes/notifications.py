from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException, NotFound

from app.services.notification_service import NotificationService

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@login_required
def list_notifications():
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    service = NotificationService(tenant_id=current_user.tenant_id)
    notifications = service.list_for_user(current_user.id, unread_only=unread_only)
    return jsonify({"success": True, "notifications": [n.to_dict() for n in notifications]})


@notifications_bp.route("", methods=["POST"])
@login_required
def create_notification():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "title_required"}), 400

    service = NotificationService(tenant_id=current_user.tenant_id)
    notification = service.create(current_user.id, title=title, message=data.get("message", ""))
    return jsonify({"success": True, "notification": notification.to_dict()}), 201


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    service = NotificationService(tenant_id=current_user.tenant_id)
    try:
        notification = service.mark_read(notification_id, current_user.id)
    except HTTPException as exc:
        return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_")}), exc.code
    return jsonify({"success": True, "notification": notification.to_dict()})
