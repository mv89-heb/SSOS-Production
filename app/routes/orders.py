import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from app.extensions import db
from app.services.order_service import OrderService
from app.services.ocr_service import OCRService, validate_upload, OCRProviderError
from app.services.permission_service import PermissionService
from app.services import google_calendar_service as gcal

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")

def _handle(exc: HTTPException):
    """Helper to format JSON error responses."""
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description
    }), exc.code

@orders_bp.route("", methods=["GET"])
@login_required
def list_orders():
    status = request.args.get("status")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        orders = service.list_orders(status=status, limit=limit, offset=offset)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "orders": [o.to_dict() for o in orders]})

@orders_bp.route("", methods=["POST"])
@login_required
def create_order():
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)
    data = request.get_json(silent=True) or {}
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.create_order(current_user, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()}), 201

@orders_bp.route("/<int:order_id>", methods=["GET"])
@login_required
def get_order(order_id):
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.get_order(order_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>", methods=["PUT"])
@login_required
def update_order(order_id):
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)
    data = request.get_json(silent=True) or {}
    if "status" in data:
        return jsonify({
            "success": False,
            "error": "use_lifecycle_endpoint",
            "message": "Status changes must go through /submit, /approve, /reject, /sent, or /complete",
        }), 400
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.update_order(current_user, order_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>", methods=["DELETE"])
@login_required
def delete_order(order_id):
    """Delete an order according to lifecycle/role rules.

    Drafts can be removed by their creator; managers/admins can remove any
    order. Google Calendar cleanup is best-effort and never blocks the DB
    deletion.
    """
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.delete_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)

    calendar_event_id = order.google_calendar_event_id
    calendar_deleted = None
    if calendar_event_id:
        try:
            gcal.delete_order_event(order)
            calendar_deleted = True
        except Exception:
            current_app.logger.exception("Google Calendar cleanup failed before order deletion: order_id=%s", order_id)
            calendar_deleted = False

    db.session.commit()
    return jsonify({"success": True, "calendar_event_deleted": calendar_deleted}), 200

@orders_bp.route("/<int:order_id>/submit", methods=["POST"])
@login_required
def submit_order(order_id):
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.submit_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/approve", methods=["POST"])
@login_required
def approve_order(order_id):
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.approve_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/reject", methods=["POST"])
@login_required
def reject_order(order_id):
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)
    data = request.get_json(silent=True) or {}
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.reject_order(current_user, order_id, reason=data.get("reason", ""))
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/sent", methods=["POST"])
@login_required
def mark_order_sent(order_id):
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.mark_sent(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/complete", methods=["POST"])
@login_required
def mark_order_completed(order_id):
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.mark_completed(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/ocr", methods=["POST"])
@login_required
def ocr_upload(order_id):
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        service.get_order(order_id)
    except HTTPException as exc:
        return _handle(exc)
    if "file" not in request.files:
        return jsonify({"success": False, "error": "no_file"}), 400
    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"success": False, "error": "no_file"}), 400
    filename = secure_filename(upload.filename)
    mime_type = upload.mimetype
    upload.stream.seek(0, os.SEEK_END)
    file_size = upload.stream.tell()
    upload.stream.seek(0)
    try:
        validate_upload(filename, mime_type, file_size, max_size=current_app.config["MAX_CONTENT_LENGTH"])
    except OCRProviderError as exc:
        return jsonify({"success": False, "error": "invalid_upload", "message": str(exc)}), 400
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    upload.save(save_path)
    result = OCRService().process_document(save_path)
    return jsonify({"success": result["status"] == "success", "result": result}), 200
