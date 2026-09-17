from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.models.order import Order
from app.models.product import Product
from app.models.supplier_offer import SupplierProductOffer
from app.repositories.supplier_repository import SupplierRepository
from app.services.order_service import OrderService


class OrderOfferIntegrationService:
    """Create a purchase order from explicit supplier-offer selections."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.supplier_repo = SupplierRepository(tenant_id)

    def create_order_from_selection(self, user, supplier_id: int, items: list[dict], notes=None) -> Order:
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            raise BadRequest("A valid supplier_id is required")
        if not isinstance(items, list) or not items:
            raise BadRequest("At least one item is required")

        self.supplier_repo.get_by_id_or_404(supplier_id)
        normalized = []
        for raw in items:
            if not isinstance(raw, dict):
                raise BadRequest("Each item must be an object")
            product_id = raw.get("product_id")
            offer_id = raw.get("supplier_offer_id")
            quantity = raw.get("quantity")
            if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
                raise BadRequest("Each item requires a valid product_id")
            if not isinstance(offer_id, int) or isinstance(offer_id, bool) or offer_id <= 0:
                raise BadRequest("Each item requires a valid supplier_offer_id")
            if isinstance(quantity, bool):
                raise BadRequest("Quantity must be a positive integer")
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise BadRequest("Quantity must be a positive integer")
            if quantity <= 0 or quantity > OrderService.MAX_LINE_QUANTITY:
                raise BadRequest(f"Quantity must be between 1 and {OrderService.MAX_LINE_QUANTITY}")

            offer = db.session.execute(
                db.select(SupplierProductOffer).where(
                    SupplierProductOffer.id == offer_id,
                    SupplierProductOffer.tenant_id == self.tenant_id,
                )
            ).scalar_one_or_none()
            if offer is None:
                raise NotFound(f"Supplier offer {offer_id} not found")
            if not offer.active:
                raise Conflict(f"Supplier offer {offer_id} is inactive")
            if offer.supplier_id != supplier_id or offer.product_id != product_id:
                raise Conflict("Supplier offer does not match the selected supplier and product")

            product = db.session.execute(
                db.select(Product).where(
                    Product.id == product_id,
                    Product.tenant_id == self.tenant_id,
                )
            ).scalar_one_or_none()
            if product is None:
                raise NotFound(f"Product {product_id} not found in your catalog")
            if not product.active:
                raise Conflict(f"Product {product_id} is inactive")

            normalized.append({
                "product_id": product_id,
                "supplier_offer_id": offer_id,
                "quantity": quantity,
            })

        return OrderService(self.tenant_id).create_order(
            user,
            {
                "supplier_id": supplier_id,
                "items": normalized,
                "notes": notes,
                "currency": "ILS",
            },
        )
