from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from app.services.admin_service import AdminService
from app.services.permission_service import PermissionService
from app.models.user import ROLE_ADMIN

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


def _require_admin():
    PermissionService.require_role_at_least(ROLE_ADMIN)


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user(user_id: int):
    try:
        _require_admin()
        user = AdminService(current_user.tenant_id, current_user.id).deactivate_user(user_id)
        from app.extensions import db
        db.session.commit()
        return jsonify({"success": True, "user": user.to_dict()})
    except HTTPException as exc:
        return _handle(exc)


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id: int):
    try:
        _require_admin()
        from app.extensions import db
        AdminService(current_user.tenant_id, current_user.id).delete_user(user_id)
        db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc:
        return _handle(exc)


@admin_bp.route("/suppliers/<int:supplier_id>/deactivate", methods=["POST"])
@login_required
def deactivate_supplier(supplier_id: int):
    try:
        _require_admin()
        supplier = AdminService(current_user.tenant_id, current_user.id).deactivate_supplier(supplier_id)
        from app.extensions import db
        db.session.commit()
        return jsonify({"success": True, "supplier": supplier.to_dict()})
    except HTTPException as exc:
        return _handle(exc)


@admin_bp.route("/suppliers/<int:supplier_id>", methods=["DELETE"])
@login_required
def delete_supplier(supplier_id: int):
    try:
        _require_admin()
        from app.extensions import db
        AdminService(current_user.tenant_id, current_user.id).delete_supplier(supplier_id)
        db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc:
        return _handle(exc)
