from datetime import datetime, timezone
from app.extensions import db

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)

    sku = db.Column(db.String(100), index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    current_price = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    currency = db.Column(db.String(3), default="ILS", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # --- Phase 1: Core Data Foundation (Product Model Upgrade) -------------
    # All nullable — existing rows/clients are unaffected; nothing here is
    # read by OrderService (Snapshot Architecture only ever copies
    # sku/name/price at order-creation time), so none of this can change
    # the numbers on an existing order.
    image_url = db.Column(db.String(500), nullable=True)
    barcode = db.Column(db.String(64), nullable=True, index=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    unit = db.Column(db.String(50), nullable=True)  # e.g. "יחידה", "קילו", "ארגז"
    units_per_carton = db.Column(db.Integer, nullable=True)
    supplier_sku = db.Column(db.String(100), nullable=True)  # supplier's own product code (distinct from our internal sku)
    current_stock = db.Column(db.Integer, nullable=True)
    min_stock = db.Column(db.Integer, nullable=True)
    recommended_stock = db.Column(db.Integer, nullable=True)

    supplier = db.relationship("Supplier", back_populates="products")
    # Phase 2: other suppliers' prices for this same product (comparison
    # data only — never read by OrderService, see SupplierProductOffer).
    supplier_offers = db.relationship(
        "SupplierProductOffer", back_populates="product", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "current_price": float(self.current_price),
            "currency": self.currency,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "image_url": self.image_url,
            "barcode": self.barcode,
            "category": self.category,
            "unit": self.unit,
            "units_per_carton": self.units_per_carton,
            "supplier_sku": self.supplier_sku,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "recommended_stock": self.recommended_stock,
        }
