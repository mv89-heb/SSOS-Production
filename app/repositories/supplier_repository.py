from sqlalchemy import select
from app.extensions import db
from app.models.supplier import Supplier
from app.repositories.base_repository import BaseRepository

class SupplierRepository(BaseRepository):
    model = Supplier

    def get_active(self):
        stmt = self._tenant_select().where(Supplier.active == True).order_by(Supplier.name.asc())
        return list(db.session.execute(stmt).scalars().all())
