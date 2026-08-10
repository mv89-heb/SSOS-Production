from datetime import datetime, timezone
from app.extensions import db

class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)

    name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(200))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    phone2 = db.Column(db.String(50))
    customer_number = db.Column(db.String(100))
    delivery_days = db.Column(db.String(100))
    order_days = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    products = db.relationship("Product", back_populates="supplier", cascade="all, delete-orphan")
    offered_products = db.relationship(
        "SupplierProductOffer", back_populates="supplier", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "phone2": self.phone2,
            "customer_number": self.customer_number,
            "delivery_days": self.delivery_days,
            "order_days": self.order_days,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
