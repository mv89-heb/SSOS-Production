from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy import select

from app.extensions import db, limiter
from app.models.tenant import Tenant
from app.models.user import User, ROLE_ADMIN, ROLE_EMPLOYEE
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.utils.validators import is_valid_email, is_strong_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@auth_bp.route("/csrf-token", methods=["GET"])
def csrf_token():
    """Issue a CSRF token tied to the current browser session."""
    return jsonify({"success": True, "csrf_token": generate_csrf()})


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    tenant_name = (data.get("tenant_name") or "").strip()
    tenant_slug = (data.get("tenant_slug") or "").strip().lower()

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "invalid_email"}), 400
    if not is_strong_password(password):
        return jsonify({
            "success": False,
            "error": "weak_password",
            "message": "Password must be at least 8 characters and include a letter and a digit",
        }), 400
    if not full_name:
        return jsonify({"success": False, "error": "full_name_required"}), 400

    tenant = None
    is_new_tenant = False

    if tenant_slug:
        tenant = db.session.execute(select(Tenant).where(Tenant.slug == tenant_slug)).scalar_one_or_none()
        if tenant is None:
            return jsonify({"success": False, "error": "tenant_not_found"}), 404
        if not tenant.active:
            return jsonify({"success": False, "error": "tenant_inactive"}), 403
    else:
        if not tenant_name:
            return jsonify({"success": False, "error": "tenant_name_or_slug_required"}), 400

        generated_slug = "-".join(tenant_name.lower().split())
        existing = db.session.execute(select(Tenant).where(Tenant.slug == generated_slug)).scalar_one_or_none()
        if existing:
            return jsonify({"success": False, "error": "tenant_already_exists"}), 409

        tenant = Tenant(name=tenant_name, slug=generated_slug, active=True)
        db.session.add(tenant)
        db.session.flush()
        is_new_tenant = True

    if UserRepository(tenant_id=tenant.id).get_by_email(email):
        return jsonify({"success": False, "error": "email_already_registered"}), 409

    role = ROLE_ADMIN if is_new_tenant else ROLE_EMPLOYEE

    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        role=role,
        active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    AuditService.log_event(
        tenant_id=tenant.id,
        user_id=user.id,
        action="auth.register",
        title=f"User {user.email} registered",
        metadata={"role": user.role, "new_tenant": is_new_tenant},
    )
    db.session.commit()

    return jsonify({"success": True, "user": user.to_dict(), "tenant": tenant.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_LOGIN"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    tenant_slug = (data.get("tenant_slug") or "").strip().lower()

    if not email or not password:
        return jsonify({"success": False, "error": "missing_credentials"}), 400

    users = db.session.execute(select(User).where(User.email == email)).scalars().all()

    if tenant_slug:
        user = next((candidate for candidate in users if candidate.tenant and candidate.tenant.slug == tenant_slug), None)
    elif len(users) == 1:
        user = users[0]
    elif len(users) > 1:
        return jsonify({
            "success": False,
            "error": "tenant_required",
            "message": "Multiple organizations use this email. Select your organization and try again.",
        }), 409
    else:
        user = None

    now = datetime.now(timezone.utc)
    if user and user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            return jsonify({
                "success": False,
                "error": "account_temporarily_locked",
                "message": "Too many failed login attempts. Try again later.",
            }), 423
        user.locked_until = None
        user.failed_login_attempts = 0
        db.session.commit()

    if not user or not user.check_password(password):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                AuditService.log_event(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    action="auth.account_locked",
                    title=f"Account temporarily locked for {email}",
                    metadata={"failed_attempts": user.failed_login_attempts, "lockout_minutes": LOCKOUT_MINUTES},
                )
            else:
                AuditService.log_event(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    action="auth.login_failed",
                    title=f"Failed login for {email}",
                    metadata={"failed_attempts": user.failed_login_attempts},
                )
            db.session.commit()
        return jsonify({"success": False, "error": "invalid_credentials"}), 401

    if not user.active:
        AuditService.log_event(tenant_id=user.tenant_id, user_id=user.id, action="auth.login_blocked", title=f"Login blocked for inactive user {email}")
        db.session.commit()
        return jsonify({"success": False, "error": "account_inactive"}), 403

    if not user.tenant or not user.tenant.active:
        AuditService.log_event(tenant_id=user.tenant_id, user_id=user.id, action="auth.login_blocked", title=f"Login blocked for inactive tenant user {email}")
        db.session.commit()
        return jsonify({"success": False, "error": "tenant_inactive"}), 403

    user.failed_login_attempts = 0
    user.locked_until = None
    login_user(user)
    user.last_login_at = now

    AuditService.log_event(tenant_id=user.tenant_id, user_id=user.id, action="auth.login", title=f"User {user.email} logged in")
    db.session.commit()

    return jsonify({"success": True, "user": user.to_dict(), "tenant": user.tenant.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user_id = current_user.id
    tenant_id = current_user.tenant_id
    email = current_user.email
    logout_user()

    AuditService.log_event(tenant_id=tenant_id, user_id=user_id, action="auth.logout", title=f"User {email} logged out")
    db.session.commit()
    return jsonify({"success": True})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({
        "success": True,
        "user": current_user.to_dict(),
        "tenant": current_user.tenant.to_dict() if current_user.tenant else None,
    })
