from flask import Blueprint, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf

from app.extensions import db, limiter
from app.models.tenant import Tenant
from app.models.user import User, VALID_ROLES, ROLE_EMPLOYEE
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.utils.validators import is_valid_email, is_strong_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/csrf-token", methods=["GET"])
def csrf_token():
    """
    Issue a CSRF token for the SPA to echo back in the X-CSRFToken header on
    every state-changing request (POST/PUT/PATCH/DELETE). GET requests are
    never CSRF-checked by Flask-WTF, so this endpoint itself needs no
    exemption. generate_csrf() ties the token to the session, so this also
    establishes the session cookie on a client's very first request — call
    it once on app load, before login.
    ---
    tags:
      - Auth
    responses:
      200:
        description: A CSRF token tied to the current session
    """
    return jsonify({"success": True, "csrf_token": generate_csrf()})


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    tenant_name = (data.get("tenant_name") or "").strip()
    tenant_slug = (data.get("tenant_slug") or "").strip().lower()
    role = data.get("role", ROLE_EMPLOYEE)

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "invalid_email"}), 400
    if not is_strong_password(password):
        return jsonify({"success": False, "error": "weak_password",
                         "message": "Password must be at least 8 characters and include a letter and a digit"}), 400
    if not full_name:
        return jsonify({"success": False, "error": "full_name_required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"success": False, "error": "invalid_role"}), 400

    # Tenant resolution: join an existing tenant by slug, or create a new one.
    tenant = None
    if tenant_slug:
        tenant = db.session.execute(
            db.select(Tenant).where(Tenant.slug == tenant_slug)
        ).scalar_one_or_none()
        if tenant is None:
            return jsonify({"success": False, "error": "tenant_not_found"}), 404
    else:
        if not tenant_name:
            return jsonify({"success": False, "error": "tenant_name_or_slug_required"}), 400
        generated_slug = tenant_name.lower().replace(" ", "-")
        existing = db.session.execute(
            db.select(Tenant).where(Tenant.slug == generated_slug)
        ).scalar_one_or_none()
        if existing:
            return jsonify({"success": False, "error": "tenant_already_exists"}), 409
        tenant = Tenant(name=tenant_name, slug=generated_slug, active=True)
        db.session.add(tenant)
        db.session.flush()
        # First user of a brand-new tenant is always its admin.
        role = "admin"

    if UserRepository(tenant_id=tenant.id).get_by_email(email):
        return jsonify({"success": False, "error": "email_already_registered"}), 409

    user = User(tenant_id=tenant.id, email=email, full_name=full_name, role=role, active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    AuditService.log_event(
        tenant_id=tenant.id, user_id=user.id, action="auth.register",
        title=f"User {user.email} registered", metadata={"role": user.role},
    )
    db.session.commit()

    return jsonify({"success": True, "user": user.to_dict(), "tenant": tenant.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(lambda: current_app.config["RATELIMIT_LOGIN"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"success": False, "error": "missing_credentials"}), 400

    user = UserRepository.get_by_email_any_tenant(email)

    # Constant-shaped response regardless of which check failed, to avoid
    # leaking whether an email exists.
    if not user or not user.active or not user.check_password(password):
        if user:
            AuditService.log_event(
                tenant_id=user.tenant_id, user_id=user.id, action="auth.login_failed",
                title=f"Failed login for {email}",
            )
            db.session.commit()
        return jsonify({"success": False, "error": "invalid_credentials"}), 401

    login_user(user)
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    AuditService.log_event(
        tenant_id=user.tenant_id, user_id=user.id, action="auth.login",
        title=f"User {user.email} logged in",
    )
    db.session.commit()

    return jsonify({"success": True, "user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user_id = current_user.id
    tenant_id = current_user.tenant_id
    email = current_user.email
    logout_user()

    AuditService.log_event(
        tenant_id=tenant_id, user_id=user_id, action="auth.logout",
        title=f"User {email} logged out",
    )
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
