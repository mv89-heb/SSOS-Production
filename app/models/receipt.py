from datetime import datetime, timezone

from app.extensions import db


RECEIPT_DRAFT = "draft"
RECEIPT_POSTED = "posted"
RECEIPT_CANCELLED = "cancelled"
VALID_RECEIPT_STATUSES = (RECEIPT_DRAFT, RECEIPT_POSTED, RECEIPT_CANCELLED)


class Receipt(db.Model):
    """A receiving document for one purchase order.

    A receipt is deliberately separate from Order status. One order can have
    multiple receipts, including partial receipts.
    """

    __tablename__ = "receipts"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "receipt_number", name="uq_receipts_tenant_receipt_number"),
        db.Index("ix_receipts_tenant_order", "tenant_id", "order_id"),
        db.Index("ix_receipts_tenant_status", "tenant_id", "status"),
        db.Index("ix_receipts_tenant_received_at", "tenant_id", "received_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    receipt_number = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=RECEIPT_DRAFT, index=True)
    received_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    received_at = db.Column(db.DateTime, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = db.relationship("Tenant")
    order = db.relationship("Order", back_populates="receipts")
    receiver = db.relationship("User")
    items = db.relationship(
        "ReceiptItem",
        back_populates="receipt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "receipt_number": self.receipt_number,
            "status": self.status,
            "received_by": self.received_by,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "notes": self.notes,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
