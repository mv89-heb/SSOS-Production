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

    supplier = db.relationship("Supplier", back_populates="products")

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
            "created_at": self.created_at.isoformat()
        }
