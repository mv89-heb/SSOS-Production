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
    def require_role_at_least(minimum_role: str):
        PermissionService.require_authenticated()
        user_rank = ROLE_RANK.get(current_user.role, 0)
        min_rank = ROLE_RANK.get(minimum_role, 99)
        if user_rank < min_rank:
            raise Forbidden(f"Requires role '{minimum_role}' or higher")

    @staticmethod
    def require_exact_role(role: str):
        PermissionService.require_authenticated()
        if current_user.role != role and current_user.role != ROLE_ADMIN:
            raise Forbidden(f"Requires role '{role}'")

    @staticmethod
    def can_manage_orders() -> bool:
        return current_user.is_authenticated and current_user.role in (ROLE_ADMIN, "manager")

    @staticmethod
    def can_delete_orders() -> bool:
        return current_user.is_authenticated and current_user.role == ROLE_ADMIN

    @staticmethod
    def require_same_tenant(resource_tenant_id: int):
        PermissionService.require_authenticated()
        if current_user.tenant_id != resource_tenant_id:
            raise Forbidden("Cross-tenant access is not permitted")
