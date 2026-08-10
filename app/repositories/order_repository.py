from sqlalchemy import select, text

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

    def get_by_id_for_update(self, order_id: int):
        """Load a tenant-scoped order with a row lock for lifecycle mutations.

        PostgreSQL honors SELECT ... FOR UPDATE and blocks concurrent requests
        from evaluating the same order transition against stale state. SQLite
        ignores the lock clause, which keeps the test/development database
        compatible while preserving the stronger production behavior.
        """
        stmt = self._tenant_select().where(Order.id == order_id).with_for_update()
        return db.session.execute(stmt).scalar_one_or_none()

    def next_order_number(self) -> str:
        """Generate the next tenant-local PO number safely on PostgreSQL.

        The advisory transaction lock serializes concurrent order-number
        allocation for the same tenant. Without it, two requests can both
        observe the same last order and generate the same number before either
        transaction commits.
        """
        if db.engine.dialect.name == "postgresql":
            db.session.execute(
                text("SELECT pg_advisory_xact_lock(:tenant_id)"),
                {"tenant_id": self.tenant_id},
            )

        stmt = (
            select(Order)
            .where(Order.tenant_id == self.tenant_id)
            .order_by(Order.id.desc())
            .limit(1)
        )
        last = db.session.execute(stmt).scalar_one_or_none()
        next_seq = (last.id + 1) if last else 1
        return f"PO-{self.tenant_id:04d}-{next_seq:06d}"
