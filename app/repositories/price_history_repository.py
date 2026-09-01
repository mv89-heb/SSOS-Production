from sqlalchemy import select

from app.extensions import db
from app.models.price_history import PriceHistory
from app.repositories.base_repository import BaseRepository


class PriceHistoryRepository(BaseRepository):
    model = PriceHistory

    def get_by_product(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        stmt = self._tenant_select().where(PriceHistory.product_id == product_id)
        if supplier_id is not None:
            stmt = stmt.where(PriceHistory.supplier_id == supplier_id)
        stmt = stmt.order_by(PriceHistory.effective_at.desc(), PriceHistory.id.desc()).limit(limit)
        return list(db.session.execute(stmt).scalars().all())

    def list_all(self, limit: int = 100):
        stmt = self._tenant_select().order_by(
            PriceHistory.effective_at.desc(), PriceHistory.id.desc()
        ).limit(limit)
        return list(db.session.execute(stmt).scalars().all())

    def add_change(self, *, product_id: int, supplier_id: int, old_price, new_price,
                   currency: str, unit: str | None, source_type: str,
                   source_document_id: int | None, effective_at, change_percent):
        history = PriceHistory(
            tenant_id=self.tenant_id,
            product_id=product_id,
            supplier_id=supplier_id,
            old_price=old_price,
            new_price=new_price,
            currency=currency,
            unit=unit,
            source_type=source_type,
            source_document_id=source_document_id,
            effective_at=effective_at,
            change_percent=change_percent,
        )
        return self.add(history)
