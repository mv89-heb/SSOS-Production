from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from werkzeug.exceptions import Conflict, HTTPException, NotFound

from app.extensions import db
from app.models.import_session import ImportSession, STATUS_FAILED
from app.models.order import Order
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import ROLE_ADMIN, User
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.order_service import OrderService
from app.services.permission_service import PermissionService

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _require_admin():
    PermissionService.require_role_at_least(ROLE_ADMIN)


@admin_bp.before_request
def _admin_guard():
    if request.method == "OPTIONS":
        return None
    try:
        _require_admin()
    except HTTPException as exc:
        return _handle(exc)
    return None


def _tenant_product(product_id: int) -> Product:
    product = db.session.execute(select(Product).where(Product.id == product_id, Product.tenant_id == current_user.tenant_id)).scalar_one_or_none()
    if product is None:
        raise NotFound("Product not found")
    return product


def _tenant_order(order_id: int) -> Order:
    order = db.session.execute(select(Order).where(Order.id == order_id, Order.tenant_id == current_user.tenant_id)).scalar_one_or_none()
    if order is None:
        raise NotFound("Order not found")
    return order


@admin_bp.route("/overview", methods=["GET"])
@login_required
def overview():
    tenant_id = current_user.tenant_id
    counts = {
        "users": db.session.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id)) or 0,
        "active_users": db.session.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id, User.active.is_(True))) or 0,
        "suppliers": db.session.scalar(select(func.count(Supplier.id)).where(Supplier.tenant_id == tenant_id)) or 0,
        "active_suppliers": db.session.scalar(select(func.count(Supplier.id)).where(Supplier.tenant_id == tenant_id, Supplier.active.is_(True))) or 0,
        "products": db.session.scalar(select(func.count(Product.id)).where(Product.tenant_id == tenant_id)) or 0,
        "active_products": db.session.scalar(select(func.count(Product.id)).where(Product.tenant_id == tenant_id, Product.active.is_(True))) or 0,
        "orders": db.session.scalar(select(func.count(Order.id)).where(Order.tenant_id == tenant_id)) or 0,
        "imports": db.session.scalar(select(func.count(ImportSession.id)).where(ImportSession.tenant_id == tenant_id)) or 0,
    }
    return jsonify({"success": True, "counts": counts})


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user(user_id: int):
    try:
        user = AdminService(current_user.tenant_id, current_user.id).deactivate_user(user_id); db.session.commit()
        return jsonify({"success": True, "user": user.to_dict()})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@login_required
def activate_user(user_id: int):
    try:
        user = AdminService(current_user.tenant_id, current_user.id).activate_user(user_id); db.session.commit()
        return jsonify({"success": True, "user": user.to_dict()})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id: int):
    try:
        AdminService(current_user.tenant_id, current_user.id).delete_user(user_id); db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/suppliers/<int:supplier_id>/deactivate", methods=["POST"])
@login_required
def deactivate_supplier(supplier_id: int):
    try:
        supplier = AdminService(current_user.tenant_id, current_user.id).deactivate_supplier(supplier_id); db.session.commit()
        return jsonify({"success": True, "supplier": supplier.to_dict()})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/suppliers/<int:supplier_id>/activate", methods=["POST"])
@login_required
def activate_supplier(supplier_id: int):
    try:
        supplier = AdminService(current_user.tenant_id, current_user.id).activate_supplier(supplier_id); db.session.commit()
        return jsonify({"success": True, "supplier": supplier.to_dict()})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/suppliers/<int:supplier_id>", methods=["DELETE"])
@login_required
def delete_supplier(supplier_id: int):
    try:
        AdminService(current_user.tenant_id, current_user.id).delete_supplier(supplier_id); db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id: int):
    product = _tenant_product(product_id)
    name = product.name; target_id = product.id; previous_active = product.active
    db.session.delete(product)
    AuditService.log_event(current_user.tenant_id, current_user.id, "admin.product_deleted", f"Permanently deleted product {name}", {"product_id": target_id, "previous_active": previous_active})
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/orders/<int:order_id>", methods=["GET"])
@login_required
def get_order(order_id: int):
    order = _tenant_order(order_id)
    return jsonify({"success": True, "order": order.to_dict()})


@admin_bp.route("/orders/<int:order_id>", methods=["PATCH"])
@login_required
def update_order(order_id: int):
    order = _tenant_order(order_id)
    data = request.get_json(silent=True) or {}
    allowed_statuses = {"draft", "submitted", "approved", "sent", "completed", "cancelled"}
    changes = {}
    if "notes" in data:
        order.notes = (data.get("notes") or "").strip() or None
        changes["notes_changed"] = True
    if "status" in data:
        status = str(data.get("status") or "").strip().lower()
        if status not in allowed_statuses:
            raise Conflict("Invalid order status")
        if status != order.status:
            changes["from_status"] = order.status
            changes["to_status"] = status
            order.status = status
    if not changes:
        return jsonify({"success": True, "order": order.to_dict(), "changed": False})
    AuditService.log_event(current_user.tenant_id, current_user.id, "admin.order_updated", f"Order {order.order_number} updated by administrator", {"order_id": order.id, **changes})
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict(), "changed": True})


@admin_bp.route("/orders/<int:order_id>", methods=["DELETE"])
@login_required
def delete_order(order_id: int):
    try:
        OrderService(current_user.tenant_id).delete_order_as_admin(current_user, order_id)
        db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc: return _handle(exc)


@admin_bp.route("/audit", methods=["GET"])
@login_required
def admin_audit():
    from app.repositories.audit_repository import AuditRepository
    limit = min(max(request.args.get("limit", 50, type=int) or 50, 1), 200)
    offset = max(request.args.get("offset", 0, type=int) or 0, 0)
    logs = AuditRepository(tenant_id=current_user.tenant_id).list_all(limit=limit, offset=offset)
    action = (request.args.get("action") or "").strip().lower()
    items = [log.to_dict() for log in logs]
    if action:
        items = [item for item in items if action in str(item.get("action", "")).lower()]
    valid, broken_id = AuditService.verify_chain(current_user.tenant_id)
    return jsonify({"success": True, "logs": items, "audit_chain_valid": valid, "first_broken_log_id": broken_id, "limit": limit, "offset": offset})


@admin_bp.route("/imports/<int:session_id>", methods=["DELETE"])
@login_required
def delete_import(session_id: int):
    session = db.session.execute(select(ImportSession).where(ImportSession.id == session_id, ImportSession.tenant_id == current_user.tenant_id)).scalar_one_or_none()
    if session is None: raise NotFound("Import session not found")
    if session.status != STATUS_FAILED: raise Conflict("Only failed import sessions can be permanently deleted. Imported or in-progress history must be retained.")
    storage_path = session.storage_path; filename = session.filename; target_id = session.id
    db.session.delete(session); db.session.flush()
    if storage_path:
        try: Path(storage_path).unlink(missing_ok=True)
        except OSError: pass
    AuditService.log_event(current_user.tenant_id, current_user.id, "admin.import_deleted", f"Deleted failed import {filename}", {"import_session_id": target_id})
    db.session.commit()
    return jsonify({"success": True})
