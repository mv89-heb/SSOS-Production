from datetime import datetime, timezone

from app.extensions import db


class SupplierProduct(db.Model):
    """A supplier-specific listing and current price, optionally linked to a master product."""
    __tablename__ = "supplier_products"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "id", name="uq_supplier_products_tenant_id_id"),
        db.CheckConstraint("price IS NULL OR price > 0", name="ck_supplier_products_positive_price"),
        db.CheckConstraint("match_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_supplier_products_match_status"),
        db.Index("ix_supplier_products_tenant_supplier", "tenant_id", "supplier_id"),
        db.Index("ix_supplier_products_tenant_master", "tenant_id", "master_product_id"),
        db.Index("ix_supplier_products_tenant_supplier_sku", "tenant_id", "supplier_id", "supplier_sku"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    master_product_id = db.Column(db.Integer, db.ForeignKey("master_products.id"), nullable=True, index=True)
    suggested_master_product_id = db.Column(db.Integer, db.ForeignKey("master_products.id"), nullable=True)
    supplier_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    supplier_sku = db.Column(db.String(120), nullable=True)
    barcode = db.Column(db.String(64), nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    unit = db.Column(db.String(50), nullable=True)
    units_per_carton = db.Column(db.Integer, nullable=True)
    normalized_name = db.Column(db.String(512), nullable=False, default="")
    match_status = db.Column(db.String(16), nullable=False, default="PENDING")
    match_confidence = db.Column(db.Numeric(5, 4), nullable=True)
    match_method = db.Column(db.String(40), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    supplier = db.relationship("Supplier")
    master_product = db.relationship("MasterProduct", back_populates="supplier_products", foreign_keys=[master_product_id])
    suggested_master_product = db.relationship("MasterProduct", foreign_keys=[suggested_master_product_id])

    def to_dict(self):
        return {
            "id": self.id, "tenant_id": self.tenant_id, "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name, "supplier_company_name": self.supplier.name if self.supplier else None, "description": self.description,
            "supplier_sku": self.supplier_sku, "barcode": self.barcode,
            "price": float(self.price) if self.price is not None else None,
            "currency": self.currency, "unit": self.unit, "units_per_carton": self.units_per_carton,
            "normalized_name": self.normalized_name, "master_product_id": self.master_product_id,
            "master_product": self.master_product.to_dict() if self.master_product else None,
            "suggested_master_product_id": self.suggested_master_product_id,
            "suggested_master_product": self.suggested_master_product.to_dict() if self.suggested_master_product else None,
            "match_status": self.match_status,
            "match_confidence": float(self.match_confidence) if self.match_confidence is not None else None,
            "match_method": self.match_method, "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
