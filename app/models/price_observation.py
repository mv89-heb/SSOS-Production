from datetime import datetime, timezone
from app.extensions import db


class PriceObservation(db.Model):
    """Immutable observation of a supplier price found in a source document."""

    __tablename__ = "price_observations"
    __table_args__ = (
        db.Index("ix_price_observation_tenant_product", "tenant_id", "product_id"),
        db.Index("ix_price_observation_tenant_supplier", "tenant_id", "supplier_id"),
        db.Index("ix_price_observation_document", "tenant_id", "source_document_id"),
        db.Index("ix_price_observation_observed_at", "tenant_id", "observed_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id = db.Column(db.Integer, nullable=True)

    observed_price = db.Column(db.Numeric(12, 4), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    unit = db.Column(db.String(50), nullable=True)
    package_quantity = db.Column(db.Numeric(12, 4), nullable=True)
    comparison_unit = db.Column(db.String(20), nullable=True)
    price_basis = db.Column(db.String(20), nullable=False, default="NET")
    source_type = db.Column(db.String(30), nullable=False, default="INVOICE")

    match_method = db.Column(db.String(30), nullable=True)
    match_confidence = db.Column(db.Numeric(5, 4), nullable=True)
    observed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product")
    supplier = db.relationship("Supplier")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "source_document_id": self.source_document_id,
            "observed_price": float(self.observed_price),
            "currency": self.currency,
            "unit": self.unit,
            "package_quantity": float(self.package_quantity) if self.package_quantity is not None else None,
            "comparison_unit": self.comparison_unit,
            "price_basis": self.price_basis,
            "source_type": self.source_type,
            "match_method": self.match_method,
            "match_confidence": float(self.match_confidence) if self.match_confidence is not None else None,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
