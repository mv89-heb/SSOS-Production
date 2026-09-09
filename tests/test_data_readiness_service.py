from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order
from app.models.price_history import PriceHistory
from app.models.price_observation import PriceObservation
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.services.data_readiness_service import ProcurementDataReadinessService


def test_snapshot_reports_factual_data_coverage(app, tenant):
    with app.app_context():
        supplier = Supplier(tenant_id=tenant.id, name="Supplier A", active=True)
        db = app.extensions["sqlalchemy"].db if False else None
