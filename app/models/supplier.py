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
    mobile = db.Column(db.String(50))
    address = db.Column(db.String(255))
    city = db.Column(db.String(120))
    tax_id = db.Column(db.String(100))
    website = db.Column(db.String(255))
    supplier_category = db.Column(db.String(120))
    payment_terms = db.Column(db.String(255))
    credit_days = db.Column(db.Integer)
    minimum_order_amount = db.Column(db.Numeric(12, 2))
    delivery_fee = db.Column(db.Numeric(12, 2))
    lead_time_days = db.Column(db.Integer)
    order_cutoff_time = db.Column(db.String(20))
    certification_details = db.Column(db.Text)
    notes = db.Column(db.Text)
    customer_number = db.Column(db.String(100))
    delivery_days = db.Column(db.String(100))
    order_days = db.Column(db.String(100))
    ordering_rules = db.Column(db.JSON, nullable=True)
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
            "mobile": self.mobile,
            "address": self.address,
            "city": self.city,
            "tax_id": self.tax_id,
            "website": self.website,
            "supplier_category": self.supplier_category,
            "payment_terms": self.payment_terms,
            "credit_days": self.credit_days,
            "minimum_order_amount": float(self.minimum_order_amount) if self.minimum_order_amount is not None else None,
            "delivery_fee": float(self.delivery_fee) if self.delivery_fee is not None else None,
            "lead_time_days": self.lead_time_days,
            "order_cutoff_time": self.order_cutoff_time,
            "certification_details": self.certification_details,
            "notes": self.notes,
            "customer_number": self.customer_number,
            "delivery_days": self.delivery_days,
            "order_days": self.order_days,
            "ordering_rules": self.ordering_rules or {},
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
