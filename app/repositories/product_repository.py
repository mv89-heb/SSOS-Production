from sqlalchemy import select
from app.extensions import db
from app.models.product import Product
from app.repositories.base_repository import BaseRepository

class ProductRepository(BaseRepository):
    model = Product

    def get_by_supplier(self, supplier_id: int):
        stmt = self._tenant_select().where(Product.supplier_id == supplier_id).order_by(Product.name.asc())
        return list(db.session.execute(stmt).scalars().all())

    def get_many_by_ids(self, product_ids: list):
        if not product_ids:
            return []
        stmt = self._tenant_select().where(Product.id.in_(product_ids))
        return list(db.session.execute(stmt).scalars().all())

    def get_all_for_matching(self):
        """Phase 3.2C: every product in the tenant's catalog, for duplicate
        detection during import validation. Uncapped (unlike list_all's
        default page size) — validation needs to compare against the
        whole catalog, not just the first page."""
        stmt = self._tenant_select()
        return list(db.session.execute(stmt).scalars().all())
