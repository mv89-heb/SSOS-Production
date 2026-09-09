from sqlalchemy import func, select

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order
from app.models.price_history import PriceHistory
from app.models.price_observation import PriceObservation
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer


class ProcurementDataReadinessService:
    """Expose factual procurement-data coverage without inventing business metrics."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    def snapshot(self) -> dict:
        tenant_id = self.tenant_id
        active_product_filter = (Product.tenant_id == tenant_id, Product.active.is_(True))
        active_offer_filter = (SupplierProductOffer.tenant_id == tenant_id, SupplierProductOffer.active.is_(True))
        active_supplier_filter = (Supplier.tenant_id == tenant_id, Supplier.active.is_(True))

        active_products = db.session.scalar(select(func.count()).select_from(Product).where(*active_product_filter)) or 0
        priced_products = db.session.scalar(
            select(func.count()).select_from(Product).where(*active_product_filter, Product.current_price > 0)
        ) or 0
        categorized_products = db.session.scalar(
            select(func.count()).select_from(Product).where(
                *active_product_filter, Product.category.is_not(None), func.trim(Product.category) != ""
            )
        ) or 0
        missing_units = db.session.scalar(
            select(func.count()).select_from(Product).where(
                *active_product_filter,
                (Product.unit.is_(None) | (func.trim(Product.unit) == "")),
            )
        ) or 0
        products_with_stock_rules = db.session.scalar(
            select(func.count()).select_from(Product).where(
                *active_product_filter,
                (Product.min_stock.is_not(None) | Product.recommended_stock.is_not(None)),
            )
        ) or 0

        active_offers = db.session.scalar(
            select(func.count()).select_from(SupplierProductOffer).where(*active_offer_filter)
        ) or 0
        covered_products = db.session.scalar(
            select(func.count(func.distinct(SupplierProductOffer.product_id))).select_from(SupplierProductOffer).where(
                *active_offer_filter
            )
        ) or 0
        covered_suppliers = db.session.scalar(
            select(func.count(func.distinct(SupplierProductOffer.supplier_id))).select_from(SupplierProductOffer).where(
                *active_offer_filter
            )
        ) or 0

        suppliers = db.session.scalar(select(func.count()).select_from(Supplier).where(*active_supplier_filter)) or 0
        price_history = db.session.scalar(
            select(func.count()).select_from(PriceHistory).where(PriceHistory.tenant_id == tenant_id)
        ) or 0
        price_observations = db.session.scalar(
            select(func.count()).select_from(PriceObservation).where(PriceObservation.tenant_id == tenant_id)
        ) or 0
        document_analyses = db.session.scalar(
            select(func.count()).select_from(DocumentAnalysis).where(DocumentAnalysis.tenant_id == tenant_id)
        ) or 0
        orders = db.session.scalar(select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id)) or 0
        priced_orders = db.session.scalar(
            select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id, Order.final_total > 0)
        ) or 0

        readiness = {
            "catalog": active_products > 0,
            "supplier_comparison": active_offers > 0 and covered_products > 0,
            "historical_prices": price_history > 0 or price_observations > 0,
            "realized_spend": priced_orders > 0,
            "stock_risk": products_with_stock_rules > 0,
        }

        return {
            "products": {
                "active": int(active_products),
                "priced": int(priced_products),
                "categorized": int(categorized_products),
                "missing_units": int(missing_units),
                "with_stock_rules": int(products_with_stock_rules),
            },
            "supplier_offers": {
                "active": int(active_offers),
                "products_covered": int(covered_products),
                "suppliers_covered": int(covered_suppliers),
            },
            "suppliers": {"active": int(suppliers)},
            "price_intelligence": {"history_rows": int(price_history), "observation_rows": int(price_observations)},
            "documents": {"analyses": int(document_analyses)},
            "orders": {"total": int(orders), "with_realized_value": int(priced_orders)},
            "readiness": readiness,
        }
