from sqlalchemy import select

from app.extensions import db
from app.models.order import Order
from app.repositories.base_repository import BaseRepository


class OrderRepository(BaseRepository):
    model = Order

    def list_by_status(self, status: str, limit: int = 100, offset: int = 0):
        stmt = (
            self._tenant_select()
            .where(Order.status == status)
            .order_by(Order.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.session.execute(stmt).scalars().all())

    def next_order_number(self) -> str:
        stmt = select(Order).where(Order.tenant_id == self.tenant_id).order_by(Order.id.desc()).limit(1)
        last = db.session.execute(stmt).scalar_one_or_none()
        next_seq = (last.id + 1) if last else 1
        return f"PO-{self.tenant_id:04d}-{next_seq:06d}"
