from __future__ import annotations

from sqlalchemy import func, select
from werkzeug.exceptions import Conflict, NotFound

from app.extensions import db
from app.models.import_session import ImportSession
from app.models.order import Order
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import ROLE_ADMIN, User
from app.services.audit_service import AuditService


class AdminService:
    """Tenant-scoped administrative lifecycle operations."""

    def __init__(self, tenant_id: int, actor_user_id: int):
        self.tenant_id = tenant_id
        self.actor_user_id = actor_user_id

    def _tenant_user(self, user_id: int) -> User:
        user = db.session.execute(select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)).scalar_one_or_none()
        if user is None:
            raise NotFound("User not found")
        return user

    def _tenant_supplier(self, supplier_id: int) -> Supplier:
        supplier = db.session.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == self.tenant_id)).scalar_one_or_none()
        if supplier is None:
            raise NotFound("Supplier not found")
        return supplier

    def _active_admin_count(self, exclude_user_id: int | None = None) -> int:
        stmt = select(func.count(User.id)).where(User.tenant_id == self.tenant_id, User.role == ROLE_ADMIN, User.active.is_(True))
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        return int(db.session.scalar(stmt) or 0)

    def deactivate_user(self, user_id: int) -> User:
        user = self._tenant_user(user_id)
        if user.id == self.actor_user_id:
            raise Conflict("You cannot deactivate your own account.")
        if user.role == ROLE_ADMIN and user.active and self._active_admin_count(user.id) == 0:
            raise Conflict("The last active administrator cannot be deactivated.")
        if user.active:
            user.active = False
            user.failed_login_attempts = 0
            user.locked_until = None
            AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.user_deactivated", f"Deactivated user {user.email}", {"target_user_id": user.id, "target_role": user.role})
        return user

    def activate_user(self, user_id: int) -> User:
        user = self._tenant_user(user_id)
        if not user.active:
            user.active = True
            AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.user_activated", f"Activated user {user.email}", {"target_user_id": user.id, "target_role": user.role})
        return user

    def delete_user(self, user_id: int) -> None:
        user = self._tenant_user(user_id)
        if user.id == self.actor_user_id:
            raise Conflict("You cannot delete your own account.")
        if user.active:
            raise Conflict("Deactivate the user before permanent deletion.")
        if user.role == ROLE_ADMIN and self._active_admin_count(user.id) == 0:
            raise Conflict("The last system administrator cannot be permanently deleted.")
        order_count = int(db.session.scalar(select(func.count(Order.id)).where(Order.tenant_id == self.tenant_id, Order.user_id == user.id)) or 0)
        import_count = int(db.session.scalar(select(func.count(ImportSession.id)).where(ImportSession.tenant_id == self.tenant_id, ImportSession.uploaded_by == user.id)) or 0)
        if order_count or import_count:
            raise Conflict(f"User has {order_count} order(s) and {import_count} import(s) in history. Keep the account deactivated instead of deleting it.")
        email = user.email
        target_id = user.id
        db.session.delete(user)
        AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.user_deleted", f"Permanently deleted user {email}", {"target_user_id": target_id, "target_role": user.role})

    def deactivate_supplier(self, supplier_id: int) -> Supplier:
        supplier = self._tenant_supplier(supplier_id)
        if supplier.active:
            supplier.active = False
            for product in supplier.products:
                product.active = False
            AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.supplier_deactivated", f"Deactivated supplier {supplier.name}", {"supplier_id": supplier.id, "products_deactivated": len(supplier.products)})
        return supplier

    def activate_supplier(self, supplier_id: int) -> Supplier:
        supplier = self._tenant_supplier(supplier_id)
        if not supplier.active:
            supplier.active = True
            AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.supplier_activated", f"Activated supplier {supplier.name}", {"supplier_id": supplier.id})
        return supplier

    def delete_supplier(self, supplier_id: int) -> None:
        supplier = self._tenant_supplier(supplier_id)
        if supplier.active:
            raise Conflict("Deactivate the supplier before permanent deletion.")
        product_count = len(supplier.products)
        offer_count = len(supplier.offered_products)
        import_count = int(db.session.scalar(select(func.count(ImportSession.id)).where(ImportSession.tenant_id == self.tenant_id, ImportSession.supplier_id == supplier.id)) or 0)
        if product_count or offer_count or import_count:
            raise Conflict(f"Supplier has {product_count} product(s), {offer_count} offer(s), or {import_count} import(s). Remove/archive dependent data first.")
        name = supplier.name
        target_id = supplier.id
        db.session.delete(supplier)
        AuditService.log_event(self.tenant_id, self.actor_user_id, "admin.supplier_deleted", f"Permanently deleted supplier {name}", {"supplier_id": target_id})
