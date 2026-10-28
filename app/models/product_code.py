from datetime import datetime, timezone

from app.extensions import db


class ProductCode(db.Model):
    """Tenant-scoped generated identifiers for labels; separate from supplier barcodes."""

    __tablename__ = "product_codes"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "code_value", name="uq_product_codes_tenant_value"),
        db.UniqueConstraint("tenant_id", "product_id", "code_type", name="uq_product_codes_product_type"),
        db.Index("ix_product_codes_tenant_product", "tenant_id", "product_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    code_type = db.Column(db.String(20), nullable=False)  # CODE128 or QR
    code_value = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "code_type": self.code_type,
            "code_value": self.code_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
