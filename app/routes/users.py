from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from werkzeug.exceptions import HTTPException, NotFound

from app.extensions import db
from app.models.user import ROLE_ADMIN, ROLE_EMPLOYEE, VALID_ROLES, User
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.utils.validators import is_strong_password, is_valid_email

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _require_admin():
    PermissionService.require_role_at_least(ROLE_ADMIN)


def _get_tenant_user(user_id: int) -> User:
    user = db.session.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("User not found")
    return user


def _active_admin_count(exclude_user_id: int | None = None) -> int:
    stmt = select(func.count(User.id)).where(
        User.tenant_id == current_user.tenant_id,
        User.role == ROLE_ADMIN,
        User.active.is_(True),
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return int(db.session.scalar(stmt) or 0)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


@users_bp.route("", methods=["GET"])
@login_required
def list_users():
    try:
        _require_admin()
    except HTTPException as exc:
        return _handle(exc)

    users = db.session.execute(
        select(User)
        .where(User.tenant_id == current_user.tenant_id)
        .order_by(User.active.desc(), User.full_name.asc(), User.email.asc())
    ).scalars().all()
    return jsonify({"success": True, "users": [u.to_dict() for u in users]})


@users_bp.route("", methods=["POST"])
@login_required
def create_user():
    try:
        _require_admin()
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    full_name = (data.get("full_name") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or ROLE_EMPLOYEE).strip().lower()

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "invalid_email"}), 400
    if not full_name:
        return jsonify({"success": False, "error": "full_name_required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"success": False, "error": "invalid_role"}), 400
    if not is_strong_password(password):
        return jsonify({
            "success": False,
            "error": "weak_password",
            "message": "Password must be at least 8 characters and include a letter and a digit",
        }), 400

    existing = db.session.execute(
        select(User).where(
            User.tenant_id == current_user.tenant_id,
            func.lower(User.email) == email,
        )
    ).scalar_one_or_none()
    if existing:
        return jsonify({"success": False, "error": "email_already_registered"}), 409

    user = User(
        tenant_id=current_user.tenant_id,
        email=email,
        full_name=full_name,
        role=role,
        active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    AuditService.log_event(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="users.create",
        title=f"Created user {user.email}",
        metadata={"target_user_id": user.id, "role": user.role},
    )
    db.session.commit()
    return jsonify({"success": True, "user": user.to_dict()}), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id: int):
    try:
        _require_admin()
    except HTTPException as exc:
        return _handle(exc)

    try:
        user = _get_tenant_user(user_id)
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    new_email = data.get("email")
    new_name = data.get("full_name")
    new_role = data.get("role")
    new_active = data.get("active")
    new_password = data.get("password")

    if new_email is not None:
        email = str(new_email).strip().lower()
        if not is_valid_email(email):
            return jsonify({"success": False, "error": "invalid_email"}), 400
        duplicate = db.session.execute(
            select(User).where(
                User.tenant_id == current_user.tenant_id,
                func.lower(User.email) == email,
                User.id != user.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            return jsonify({"success": False, "error": "email_already_registered"}), 409
        user.email = email

    if new_name is not None:
        full_name = str(new_name).strip()
        if not full_name:
            return jsonify({"success": False, "error": "full_name_required"}), 400
        user.full_name = full_name

    if new_role is not None:
        role = str(new_role).strip().lower()
        if role not in VALID_ROLES:
            return jsonify({"success": False, "error": "invalid_role"}), 400
        if user.id == current_user.id and role != ROLE_ADMIN:
            return jsonify({"success": False, "error": "cannot_remove_own_admin_role"}), 409
        if user.role == ROLE_ADMIN and role != ROLE_ADMIN and user.active and _active_admin_count(user.id) == 0:
            return jsonify({"success": False, "error": "last_admin_protected"}), 409
        user.role = role

    if new_active is not None:
        active = _parse_bool(new_active)
        if active is None:
            return jsonify({"success": False, "error": "invalid_active_value"}), 400
        if user.id == current_user.id and not active:
            return jsonify({"success": False, "error": "cannot_deactivate_self"}), 409
        if user.role == ROLE_ADMIN and user.active and not active and _active_admin_count(user.id) == 0:
            return jsonify({"success": False, "error": "last_admin_protected"}), 409
        user.active = active

    if new_password is not None:
        password = str(new_password)
        if not is_strong_password(password):
            return jsonify({
                "success": False,
                "error": "weak_password",
                "message": "Password must be at least 8 characters and include a letter and a digit",
            }), 400
        user.set_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None

    AuditService.log_event(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="users.update",
        title=f"Updated user {user.email}",
        metadata={"target_user_id": user.id},
    )
    db.session.commit()
    return jsonify({"success": True, "user": user.to_dict()})
