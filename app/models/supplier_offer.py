from datetime import datetime, timezone
from app.extensions import db


class SupplierProductOffer(db.Model):
    """A tenant-scoped supplier price that can be selected for a purchase order."""
    __tablename__ = "supplier_product_offers"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "product_id", "supplier_id", name="uq_offer_tenant_product_supplier"),
        db.CheckConstraint("price >= 0", name="ck_supplier_offers_price_nonnegative"),
        db.CheckConstraint(
            "units_per_carton IS NULL OR units_per_carton > 0",
            name="ck_supplier_offers_units_per_carton_positive",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)

    supplier_sku = db.Column(db.String(100), nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="ILS", nullable=False)
    unit = db.Column(db.String(50), nullable=True)
    units_per_carton = db.Column(db.Integer, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    product = db.relationship("Product", back_populates="supplier_offers")
    supplier = db.relationship("Supplier", back_populates="offered_products")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "supplier_sku": self.supplier_sku,
            "price": float(self.price),
            "currency": self.currency,
            "unit": self.unit,
            "units_per_carton": self.units_per_carton,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
