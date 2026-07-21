from werkzeug.exceptions import Conflict, BadRequest, NotFound

from app.repositories.supplier_repository import SupplierRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_offer_repository import SupplierOfferRepository
from app.services.audit_service import AuditService


class CatalogService:
    """
    Suppliers and Products. Products here are the *live* catalog — current
    name/price/active flag. Orders never read from this service after
    creation: OrderService copies each line item's product_id/sku/name/
    price into the order's own `items` JSON at creation time (and freezes
    it permanently into `snapshot` on submit). So nothing here can ever
    rewrite an existing order's numbers — see update_product/delete_product.
    """

    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.supplier_repo = SupplierRepository(tenant_id)
        self.product_repo = ProductRepository(tenant_id)
        self.offer_repo = SupplierOfferRepository(tenant_id)

    # ------------------------------------------------------------------
    # Suppliers
    # ------------------------------------------------------------------
    def list_suppliers(self, active_only=False):
        if active_only:
            return self.supplier_repo.get_active()
        return self.supplier_repo.list_all()

    def create_supplier(self, data: dict):
        supplier = self.supplier_repo.model(tenant_id=self.tenant_id, **data)
        self.supplier_repo.add(supplier)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.supplier_created",
            f"Created supplier {supplier.name}", {"supplier_id": supplier.id}
        )
        return supplier

    def get_supplier(self, supplier_id: int):
        """Returns the supplier only if it belongs to the current tenant;
        raises 404 otherwise."""
        return self.supplier_repo.get_by_id_or_404(supplier_id)

    def update_supplier(self, supplier_id: int, data: dict):
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)
        for field in ("name", "contact_name", "email", "phone", "active"):
            if field in data:
                setattr(supplier, field, data[field])

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.supplier_updated",
            f"Updated supplier {supplier.name}", {"supplier_id": supplier.id}
        )
        return supplier

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------
    def list_products(self, supplier_id: int = None, active_only: bool = False):
        """Tenant-scoped (ProductRepository -> BaseRepository._tenant_select).
        Filters by supplier_id and/or active flag when given."""
        if supplier_id is not None:
            # get_by_supplier already applies the tenant filter.
            products = self.product_repo.get_by_supplier(supplier_id)
        else:
            products = self.product_repo.list_all(limit=500)

        if active_only:
            products = [p for p in products if p.active]
        return products

    def get_product(self, product_id: int):
        """Returns the product only if it belongs to the current tenant;
        raises 404 otherwise."""
        return self.product_repo.get_by_id_or_404(product_id)

    # Fields a client may set on a product. Both create and update funnel
    # through this so a request with an unexpected key can never reach the
    # model constructor directly (that used to be possible on create — an
    # unrecognized kwarg there raises a raw TypeError instead of a clean
    # 400/422).
    PRODUCT_FIELDS = (
        "name", "sku", "description", "current_price", "currency", "active",
        "image_url", "barcode", "category", "unit", "units_per_carton",
        "supplier_sku", "current_stock", "min_stock", "recommended_stock",
    )

    def create_product(self, data: dict):
        # BaseRepository ensures supplier_id must belong to same tenant
        self.supplier_repo.get_by_id_or_404(data.get('supplier_id'))
        fields = {k: v for k, v in data.items() if k in self.PRODUCT_FIELDS}
        product = self.product_repo.model(tenant_id=self.tenant_id, supplier_id=data.get('supplier_id'), **fields)
        self.product_repo.add(product)
        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_created",
            f"Created product {product.name}", {"product_id": product.id}
        )
        return product

    def update_product(self, product_id: int, data: dict):
        """Changes the live catalog entry only. Existing orders keep the
        product_name/sku/unit_price they captured at creation time in their
        own `items` JSON — this never touches those rows, which is exactly
        what preserves Snapshot Integrity."""
        product = self.product_repo.get_by_id_or_404(product_id)

        for field in self.PRODUCT_FIELDS:
            if field in data:
                setattr(product, field, data[field])

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_updated",
            f"Updated product {product.name}", {"product_id": product.id}
        )
        return product

    def delete_product(self, product_id: int):
        """Hard-deletes the catalog entry. Orders already created against
        this product are unaffected — they hold a copied snapshot, not a
        foreign key that requires the product to still exist."""
        product = self.product_repo.get_by_id_or_404(product_id)

        AuditService.log_event(
            self.tenant_id, self.user_id, "catalog.product_deleted",
            f"Deleted product {product.name}", {"product_id": product.id, "sku": product.sku}
        )
        self.product_repo.delete(product)

    # ------------------------------------------------------------------
    # Phase 2: Supplier Catalog Engine — alternate-supplier price offers
    # ------------------------------------------------------------------
    # Comparison data only. Order creation (OrderService) never reads this
    # table — it still snapshots Product.current_price/supplier_id exactly
    # as before, so nothing here can change an existing or future order's
    # numbers unless a manager explicitly edits the product's own price.

    OFFER_FIELDS = ("supplier_sku", "price", "currency", "unit", "units_per_carton", "active")

    def list_offers(self, product_id: int):
        """Confirms the product belongs to this tenant, then returns its
        alternate-supplier offers (cheapest first)."""
        self.product_repo.get_by_id_or_404(product_id)
        return self.offer_repo.get_by_product(product_id)

    def create_offer(self, product_id: int, data: dict):
        product = self.product_repo.get_by_id_or_404(product_id)
        supplier_id = data.get("supplier_id")
        supplier = self.supplier_repo.get_by_id_or_404(supplier_id)

        if supplier_id == product.supplier_id:
            raise BadRequest("This supplier already owns the product as its primary listing.")
        if self.offer_repo.get_by_product_and_supplier(product_id, supplier_id):
            raise Conflict("This supplier already has a price on file for this product.")
        if data.get("price") is None or float(data["price"]) < 0:
            raise BadRequest("price is required and must not be negative.")

        fields = {k: v for k, v in data.items() if k in self.OFFER_FIELDS}
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
        self.product_repo.get_by_id_or_404(product_id)
        offer = self.offer_repo.get_by_id_or_404(offer_id)
        if offer.product_id != product_id:
            raise NotFound("SupplierProductOffer not found")

        if "price" in data and data["price"] is not None and float(data["price"]) < 0:
            raise BadRequest("price must not be negative.")

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
