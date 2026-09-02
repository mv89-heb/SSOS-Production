from app.extensions import db
from app.models.price_observation import PriceObservation


class PriceObservationRepository:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
    def create(self, **kwargs) -> PriceObservation:
        row = PriceObservation(tenant_id=self.tenant_id, **kwargs)
        db.session.add(row)
        return row
    def get_by_product(self, product_id: int, supplier_id: int | None = None, limit: int = 100):
        query = PriceObservation.query.filter_by(tenant_id=self.tenant_id, product_id=product_id)
        if supplier_id is not None:
            query = query.filter_by(supplier_id=supplier_id)
        return query.order_by(PriceObservation.observed_at.desc(), PriceObservation.id.desc()).limit(limit).all()
    def get_recent(self, product_id: int, supplier_id: int, limit: int = 5):
        return PriceObservation.query.filter_by(tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id).order_by(PriceObservation.observed_at.desc(), PriceObservation.id.desc()).limit(limit).all()
    def list_all(self, limit: int = 100):
        return PriceObservation.query.filter_by(tenant_id=self.tenant_id).order_by(PriceObservation.observed_at.desc(), PriceObservation.id.desc()).limit(limit).all()
