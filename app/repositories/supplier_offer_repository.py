from sqlalchemy import select
from app.extensions import db
from app.models.supplier_offer import SupplierProductOffer
from app.repositories.base_repository import BaseRepository


class SupplierOfferRepository(BaseRepository):
    model = SupplierProductOffer

    def get_by_product(self, product_id: int):
        """All alternate-supplier offers on file for one product, cheapest
        first — tenant-scoped via _tenant_select."""
        stmt = (
            self._tenant_select()
            .where(SupplierProductOffer.product_id == product_id)
            .order_by(SupplierProductOffer.price.asc())
        )
        return list(db.session.execute(stmt).scalars().all())

    def get_by_product_and_supplier(self, product_id: int, supplier_id: int):
        stmt = self._tenant_select().where(
            SupplierProductOffer.product_id == product_id,
            SupplierProductOffer.supplier_id == supplier_id,
        )
        return db.session.execute(stmt).scalar_one_or_none()

    def count_all(self) -> int:
        """Phase 3.2D: tenant-wide offer count, for the pre-commit snapshot."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(SupplierProductOffer).where(
            SupplierProductOffer.tenant_id == self.tenant_id
        )
        return db.session.execute(stmt).scalar_one()
