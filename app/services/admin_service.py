from __future__ import annotations

from sqlalchemy import func, select
from werkzeug.exceptions import Conflict, NotFound

from app.extensions import db
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.models.user import ROLE_ADMIN, User
from app.services.audit_service import AuditService


class AdminService:
    """Tenant-scoped, destructive administrative operations.

    Hard deletion is intentionally conservative. Business records with
    dependencies are deactivated/archived rather than cascaded away.
    """

    def __init__(self, tenant_id: int, actor_user_id: int):
        self.tenant_id = tenant_id
        self.actor_user_id = actor_user_id

    def _tenant_user(self, user_id: int) -> User:
        user = db.session.execute(
            select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)
        ).scalar_one_or_none()
        if user is None:
            raise NotFound("User not found")
        return user

    def _active_admin_count(self, exclude_user_id: int | None = None) -> int:
        stmt = select(func.count(User.id)).where(
            User.tenant_id == self.tenant_id,
            User.role == ROLE_ADMIN,
            User.active.is_(True),
        )
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
            AuditService.log_event(
                self.tenant_id,
                self.actor_user_id,
                "admin.user_deactivated",
                f"Deactivated user {user.email}",
                {"target_user_id": user.id, "target_role": user.role},
            )
        return user

    def delete_user(self, user_id: int) -> None:
        user = self._tenant_user(user_id)
        if user.id == self.actor_user_id:
            raise Conflict("You cannot delete your own account.")
        if user.role == ROLE_ADMIN and user.active and self._active_admin_count(user.id) == 0:
            raise Conflict("The last active administrator cannot be deleted.")
        if user.active:
            raise Conflict("Deactivate the user before permanent deletion.")

        AuditService.log_event(
            self.tenant_id,
            self.actor_user_id,
            "admin.user_deleted",
            f"Permanently deleted user {user.email}",
            {"target_user_id": user.id, "target_role": user.role},
        )
        db.session.delete(user)

    def deactivate_supplier(self, supplier_id: int) -> Supplier:
        supplier = db.session.execute(
            select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.tenant_id == self.tenant_id,
            )
        ).scalar_one_or_none()
        if supplier is None:
            raise NotFound("Supplier not found")

        if supplier.active:
            supplier.active = False
            for product in supplier.products:
                product.active = False
            AuditService.log_event(
                self.tenant_id,
                self.actor_user_id,
                "admin.supplier_deactivated",
                f"Deactivated supplier {supplier.name}",
                {"supplier_id": supplier.id, "products_deactivated": len(supplier.products)},
            )
        return supplier

    def delete_supplier(self, supplier_id: int) -> None:
        supplier = db.session.execute(
            select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.tenant_id == self.tenant_id,
            )
        ).scalar_one_or_none()
        if supplier is None:
            raise NotFound("Supplier not found")

        product_count = int(
            db.session.scalar(
                select(func.count(Product.id)).where(
                    Product.tenant_id == self.tenant_id,
                    Product.supplier_id == supplier.id,
                )
            )
            or 0
        )
        offer_count = int(
            db.session.scalar(
                select(func.count(SupplierProductOffer.id)).where(
                    SupplierProductOffer.tenant_id == self.tenant_id,
                    SupplierProductOffer.supplier_id == supplier.id,
                )
            )
            or 0
        )
        if product_count or offer_count:
            raise Conflict(
                "Supplier cannot be permanently deleted while catalog records depend on it. "
                "Deactivate it instead."
            )

        AuditService.log_event(
            self.tenant_id,
            self.actor_user_id,
            "admin.supplier_deleted",
            f"Permanently deleted supplier {supplier.name}",
            {"supplier_id": supplier.id},
        )
        db.session.delete(supplier)
