from datetime import datetime, timezone

from app.extensions import db

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_SENT = "sent"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
VALID_STATUSES = (
    STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED,
    STATUS_SENT, STATUS_COMPLETED, STATUS_CANCELLED,
)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    order_number = db.Column(db.String(40), nullable=False, index=True)

    # Supplier information
    supplier_name = db.Column(db.String(200), nullable=False)
    supplier_contact = db.Column(db.String(200))
    supplier_email = db.Column(db.String(255))

    status = db.Column(db.String(20), default=STATUS_DRAFT, nullable=False, index=True)

    # Monetary totals
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    discount_total = db.Column(db.Numeric(12, 2), default=0)
    tax_total = db.Column(db.Numeric(12, 2), default=0)
    final_total = db.Column(db.Numeric(12, 2), default=0)
    currency = db.Column(db.String(3), default="ILS")

    # Product / line-item information, stored as structured JSON at write time
    items = db.Column(db.JSON, default=list)

    # Immutable snapshot captured once the order is submitted (see SnapshotService).
    # Freezes prices/names/promotions as they were at that moment for historical accuracy.
    snapshot = db.Column(db.JSON, nullable=True)
    snapshot_taken_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = db.relationship("Tenant", back_populates="orders")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "order_number": self.order_number,
            "supplier_name": self.supplier_name,
            "supplier_contact": self.supplier_contact,
            "supplier_email": self.supplier_email,
            "status": self.status,
            "subtotal": float(self.subtotal) if self.subtotal is not None else 0.0,
            "discount_total": float(self.discount_total) if self.discount_total is not None else 0.0,
            "tax_total": float(self.tax_total) if self.tax_total is not None else 0.0,
            "final_total": float(self.final_total) if self.final_total is not None else 0.0,
            "currency": self.currency,
            "items": self.items or [],
            "snapshot": self.snapshot,
            "snapshot_taken_at": self.snapshot_taken_at.isoformat() if self.snapshot_taken_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Order {self.order_number} tenant={self.tenant_id}>"
