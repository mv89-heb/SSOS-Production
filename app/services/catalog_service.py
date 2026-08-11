import math

from werkzeug.exceptions import Conflict, BadRequest, NotFound

from app.repositories.supplier_repository import SupplierRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_offer_repository import SupplierOfferRepository
from app.services.audit_service import AuditService
from app.utils.validators import validate_product_payload


class CatalogService:
    """Tenant-scoped supplier/product catalog operations."""

    SUPPLIER_FIELDS = (
        "name", "contact_name", "email", "phone", "phone2",
        "customer_number", "delivery_days", "order_days", "active",
    )

    PRODUCT_FIELDS = (
        "name", "sku", "description", "current_price", "currency", "active",
        "image_url", "barcode", "category", "unit", "units_per_carton",
        "supplier_sku", "current_stock", "min_stock", "recommended_stock",
    )

    OFFER_FIELDS = ("supplier_sku", "price", "currency", "unit", "units_per_carton", "active")

    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.supplier_repo = SupplierRepository(tenant_id)
        self.product_repo = ProductRepository(tenant_id)
        self.offer_repo = SupplierOfferRepository(tenant_id)

    def list_suppliers(self, active_only=False):
        return self.supplier_repo.get_active() if active_only else self.supplier_repo.list_all()

    def create_supplier(self, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Supplier payload must be an object")
        name = str(data.get("name") or "").strip()
        if not name:
            raise BadRequest("Supplier name is required")
        if len(name) > 200:
            raise BadRequest("Supplier name is too long")

        fields = {k: v for k, v in data.items() if k in self.SUPPLIER_FIELDS}
        fields["name"] = name
        supplier = self.supplier_repo.model(tenant_id=self.tenant_id, **fields)
        self.supplier_repo.add(supplier)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.supplier_created",
            f"Created supplier {supplier.name}", {"supplier_id": supplier.id},
        )
        return supplier

    def get_supplier(self, supplier_id: int):
        return self.supplier_repo.get_by_id_or_404(supplier_id)

    def update_supplier(self, supplier_id: int, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Supplier payload must be an object")
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)
        if "name" in data:
            name = str(data.get("name") or "").strip()
            if not name:
                raise BadRequest("Supplier name is required")
            if len(name) > 200:
                raise BadRequest("Supplier name is too long")
        for field in self.SUPPLIER_FIELDS:
            if field in data:
                setattr(supplier, field, data[field])

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.supplier_updated",
            f"Updated supplier {supplier.name}", {"supplier_id": supplier.id},
        )
        return supplier

    def list_products(self, supplier_id: int = None, active_only: bool = False):
        if supplier_id is not None:
            products = self.product_repo.get_by_supplier(supplier_id)
        else:
            products = self.product_repo.list_all(limit=500)
        return [p for p in products if p.active] if active_only else products

    def get_product(self, product_id: int):
        return self.product_repo.get_by_id_or_404(product_id)

    def _validate_product_identity(self, data: dict, exclude_product_id: int | None = None):
        """Prevent duplicate tenant-scoped SKU/barcode before the DB write.

        The fields remain nullable, so empty values are intentionally ignored.
        This application-level guard protects existing databases even before a
        future unique database index is installed.
        """
        sku = data.get("sku")
        barcode = data.get("barcode")

        normalized_sku = str(sku).strip() if sku is not None else ""
        normalized_barcode = str(barcode).strip() if barcode is not None else ""

        if not normalized_sku and not normalized_barcode:
            return

        for product in self.product_repo.get_all_for_matching():
            if exclude_product_id is not None and product.id == exclude_product_id:
                continue

            if normalized_sku and product.sku and product.sku.strip().casefold() == normalized_sku.casefold():
                raise Conflict(f'SKU "{normalized_sku}" is already used by another product.')

            if normalized_barcode and product.barcode and product.barcode.strip() == normalized_barcode:
                raise Conflict(f'Barcode "{normalized_barcode}" is already used by another product.')

    def create_product(self, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Product payload must be an object")
        supplier_id = data.get("supplier_id")
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            raise BadRequest("A valid supplier_id is required")
        self.supplier_repo.get_by_id_or_404(supplier_id)
        validation_error = validate_product_payload(data)
        if validation_error:
            raise BadRequest(validation_error)
        self._validate_product_identity(data)

        fields = {k: v for k, v in data.items() if k in self.PRODUCT_FIELDS}
        if fields.get("sku") is not None:
            fields["sku"] = str(fields["sku"]).strip() or None
        if fields.get("barcode") is not None:
            fields["barcode"] = str(fields["barcode"]).strip() or None

        product = self.product_repo.model(tenant_id=self.tenant_id, supplier_id=supplier_id, **fields)
        self.product_repo.add(product)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_created",
            f"Created product {product.name}", {"product_id": product.id},
        )
        return product

    def update_product(self, product_id: int, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Product payload must be an object")
        product = self.product_repo.get_by_id_or_404(product_id)
        if "supplier_id" in data:
            supplier_id = data["supplier_id"]
            if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
                raise BadRequest("supplier_id must be a positive integer")
            self.supplier_repo.get_by_id_or_404(supplier_id)
        validation_error = validate_product_payload(data)
        if validation_error:
            raise BadRequest(validation_error)

        identity_data = {
            "sku": data["sku"] if "sku" in data else product.sku,
            "barcode": data["barcode"] if "barcode" in data else product.barcode,
        }
        self._validate_product_identity(identity_data, exclude_product_id=product.id)

        for field in self.PRODUCT_FIELDS:
            if field in data:
                value = data[field]
                if field in ("sku", "barcode") and value is not None:
                    value = str(value).strip() or None
                setattr(product, field, value)

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_updated",
            f"Updated product {product.name}", {"product_id": product.id},
        )
        return product

    def delete_product(self, product_id: int):
        product = self.product_repo.get_by_id_or_404(product_id)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_deleted",
            f"Deleted product {product.name}", {"product_id": product.id, "sku": product.sku},
        )
        self.product_repo.delete(product)

    def list_offers(self, product_id: int):
        self.product_repo.get_by_id_or_404(product_id)
        return self.offer_repo.get_by_product(product_id)

    def create_offer(self, product_id: int, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Offer payload must be an object")
        product = self.product_repo.get_by_id_or_404(product_id)
        supplier_id = data.get("supplier_id")
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            raise BadRequest("A valid supplier_id is required")
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)

        if supplier_id == product.supplier_id:
            raise BadRequest("This supplier already owns the product as its primary listing.")
        if self.offer_repo.get_by_product_and_supplier(product_id, supplier_id):
            raise Conflict("This supplier already has a price on file for this product.")
        try:
            price = float(data["price"])
        except (KeyError, TypeError, ValueError):
            raise BadRequest("price is required and must be a number")
        if not math.isfinite(price):
            raise BadRequest("price must be a finite number")
        if price < 0:
            raise BadRequest("price must not be negative.")

        fields = {k: v for k, v in data.items() if k in self.OFFER_FIELDS}
        fields["price"] = price
        offer = self.offer_repo.model(
            tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id, **fields
        )
        self.offer_repo.add(offer)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.offer_created",
            f"Added {supplier.name} as a price source for {product.name}",
            {"product_id": product_id, "supplier_id": supplier_id, "price": float(offer.price)},
        )
        return offer

    def update_offer(self, product_id: int, offer_id: int, data: dict):
        if not isinstance(data, dict):
            raise BadRequest("Offer payload must be an object")
        self.product_repo.get_by_id_or_404(product_id)
        offer = self.offer_repo.get_by_id_or_404(offer_id)
        if offer.product_id != product_id:
            raise NotFound("SupplierProductOffer not found")

        if "supplier_id" in data:
            supplier_id = data["supplier_id"]
            if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
                raise BadRequest("supplier_id must be a positive integer")
            self.supplier_repo.get_by_id_or_404(supplier_id)
            if supplier_id == offer.product.supplier_id:
                raise BadRequest("The primary product supplier cannot also be an alternate offer")
            duplicate = self.offer_repo.get_by_product_and_supplier(product_id, supplier_id)
            if duplicate and duplicate.id != offer.id:
                raise Conflict("This supplier already has a price on file for this product.")

        if "price" in data:
            try:
                price = float(data["price"])
            except (TypeError, ValueError):
                raise BadRequest("price must be a number")
            if not math.isfinite(price):
                raise BadRequest("price must be a finite number")
            if price < 0:
                raise BadRequest("price must not be negative.")
            data = {**data, "price": price}

        for field in self.OFFER_FIELDS:
            if field in data:
                setattr(offer, field, data[field])

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.offer_updated",
            f"Updated {offer.supplier.name}'s price for {offer.product.name}",
            {"product_id": product_id, "offer_id": offer.id},
        )
        return offer

    def delete_offer(self, product_id: int, offer_id: int):
        self.product_repo.get_by_id_or_404(product_id)
        offer = self.offer_repo.get_by_id_or_404(offer_id)
        if offer.product_id != product_id:
            raise NotFound("SupplierProductOffer not found")

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.offer_deleted",
            f"Removed {offer.supplier.name} as a price source for {offer.product.name}",
            {"product_id": product_id, "offer_id": offer.id},
        )
        self.offer_repo.delete(offer)
