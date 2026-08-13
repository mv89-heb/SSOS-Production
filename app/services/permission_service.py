from flask_login import current_user
from werkzeug.exceptions import Forbidden, Unauthorized

from app.models.user import ROLE_RANK, ROLE_ADMIN


class PermissionService:
    """Central RBAC decision point. Routes call this instead of checking role strings."""

    @staticmethod
    def require_authenticated():
        if not current_user.is_authenticated:
            raise Unauthorized("Authentication required")

    @staticmethod
    def _normalized_role(role) -> str:
        return str(role or "").strip().lower()

    @staticmethod
    def require_role_at_least(minimum_role: str):
        PermissionService.require_authenticated()
        user_role = PermissionService._normalized_role(current_user.role)
        required_role = PermissionService._normalized_role(minimum_role)
        user_rank = ROLE_RANK.get(user_role, 0)
        min_rank = ROLE_RANK.get(required_role, 99)
        if user_rank < min_rank:
            raise Forbidden(f"Requires role '{required_role}' or higher")

    @staticmethod
    def require_exact_role(role: str):
        PermissionService.require_authenticated()
        current_role = PermissionService._normalized_role(current_user.role)
        required_role = PermissionService._normalized_role(role)
        if current_role != required_role and current_role != ROLE_ADMIN:
            raise Forbidden(f"Requires role '{required_role}'")

    @staticmethod
    def can_manage_orders() -> bool:
        role = PermissionService._normalized_role(current_user.role)
        return current_user.is_authenticated and role in (ROLE_ADMIN, "manager")

    @staticmethod
    def can_delete_orders() -> bool:
        role = PermissionService._normalized_role(current_user.role)
        return current_user.is_authenticated and role == ROLE_ADMIN

    @staticmethod
    def require_same_tenant(resource_tenant_id: int):
        PermissionService.require_authenticated()
        if current_user.tenant_id != resource_tenant_id:
            raise Forbidden("Cross-tenant access is not permitted")
