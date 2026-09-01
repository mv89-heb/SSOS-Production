from datetime import datetime, timezone
from app.extensions import db


class PriceHistory(db.Model):
    """Immutable record of an accepted supplier price change."""

    __tablename__ = "price_history"
    __table_args__ = (
        db.Index("ix_price_history_tenant_product", "tenant_id", "product_id"),
        db.Index("ix_price_history_tenant_supplier", "tenant_id", "supplier_id"),
        db.Index("ix_price_history_effective_at", "tenant_id", "effective_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)

    old_price = db.Column(db.Numeric(12, 2), nullable=True)
    new_price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    unit = db.Column(db.String(50), nullable=True)

    source_type = db.Column(db.String(30), nullable=False, default="MANUAL")
    source_document_id = db.Column(db.Integer, nullable=True)
    effective_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    change_percent = db.Column(db.Numeric(10, 4), nullable=True)

    product = db.relationship("Product")
    supplier = db.relationship("Supplier")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "old_price": float(self.old_price) if self.old_price is not None else None,
            "new_price": float(self.new_price),
            "currency": self.currency,
            "unit": self.unit,
            "source_type": self.source_type,
            "source_document_id": self.source_document_id,
            "effective_at": self.effective_at.isoformat() if self.effective_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "change_percent": float(self.change_percent) if self.change_percent is not None else None,
        }
