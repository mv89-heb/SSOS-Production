"""Granular permission policy primitives.

This module is deliberately separate from the existing role guard until the
user model and admin API can persist per-user overrides in a reviewed change.
"""
from flask_login import current_user
from werkzeug.exceptions import Forbidden

ROLE_DEFAULTS = {
    "employee": {
        "orders.view": True,
        "orders.create": True,
        "orders.edit": True,
        "orders.approve": True,
        "orders.reject": False,
        "orders.mark_sent": True,
        "orders.complete": True,
        "orders.delete": False,
        "catalog.view": True,
        "catalog.manage": False,
        "inventory.view": True,
        "inventory.count": True,
        "documents.view": True,
        "documents.upload": True,
        "documents.process": False,
        "reports.view": True,
        "reports.export": False,
        "users.manage": False,
        "permissions.manage": False,
        "audit.view": False,
    },
    "manager": {
        "orders.view": True,
        "orders.create": True,
        "orders.edit": True,
        "orders.approve": True,
        "orders.reject": True,
        "orders.mark_sent": True,
        "orders.complete": True,
        "orders.delete": False,
        "catalog.view": True,
        "catalog.manage": True,
        "inventory.view": True,
        "inventory.count": True,
        "documents.view": True,
        "documents.upload": True,
        "documents.process": True,
        "reports.view": True,
        "reports.export": True,
        "users.manage": False,
        "permissions.manage": False,
        "audit.view": False,
    },
    "admin": {"*": True},
}


def effective_permissions(user):
    """Return role defaults plus valid, explicitly stored boolean overrides."""
    role = str(getattr(user, "role", "") or "").strip().lower()
    permissions = dict(ROLE_DEFAULTS.get(role, {}))
    if role == "admin":
        return {"*": True, **permissions}
    overrides = getattr(user, "permissions", None) or {}
    if not isinstance(overrides, dict):
        return permissions
    for key, value in overrides.items():
        if key in permissions and isinstance(value, bool):
            permissions[key] = value
    return permissions


def has_permission(permission, user=None):
    """Fail closed for anonymous or inactive users."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "active", True):
        return False
    effective = effective_permissions(user)
    return effective.get("*") is True or effective.get(permission) is True


def require_permission(permission):
    if not has_permission(permission):
        raise Forbidden(f"Permission required: {permission}")
