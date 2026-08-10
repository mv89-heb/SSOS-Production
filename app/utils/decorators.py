from functools import wraps

from flask import jsonify
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.services.permission_service import PermissionService


def role_required(minimum_role: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                PermissionService.require_role_at_least(minimum_role)
            except HTTPException as exc:
                return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def tenant_scoped(fn):
    """Marks a route as requiring an authenticated user whose tenant_id will be
    used for every downstream repository call. Kept separate from role_required
    so routes can express "any authenticated tenant member" without a role floor."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "unauthorized", "message": "Authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper
