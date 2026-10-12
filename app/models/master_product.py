from datetime import datetime, timezone

from app.extensions import db


class MasterProduct(db.Model):
    """Canonical tenant-scoped product identity shared by supplier listings."""
    __tablename__ = "master_products"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "id", name="uq_master_products_tenant_id_id"),
        db.Index("ix_master_products_tenant_normalized_name", "tenant_id", "normalized_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    canonical_name = db.Column(db.String(255), nullable=False)
    normalized_name = db.Column(db.String(512), nullable=False)
    brand = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(64), nullable=True)
    base_unit = db.Column(db.String(30), nullable=True)
    package_size = db.Column(db.Numeric(12, 4), nullable=True)
    package_unit = db.Column(db.String(30), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    supplier_products = db.relationship("SupplierProduct", back_populates="master_product", foreign_keys="SupplierProduct.master_product_id")

    def to_dict(self):
        return {
            "id": self.id, "tenant_id": self.tenant_id,
            "canonical_name": self.canonical_name, "normalized_name": self.normalized_name,
            "brand": self.brand, "category": self.category, "barcode": self.barcode,
            "base_unit": self.base_unit,
            "package_size": float(self.package_size) if self.package_size is not None else None,
            "package_unit": self.package_unit, "active": self.active,
            "supplier_product_count": len(self.supplier_products or []),
        }
