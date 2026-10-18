from datetime import datetime, timezone

from app.extensions import db


class ReceiptItem(db.Model):
    """Quantity received for a specific purchase-order line."""

    __tablename__ = "receipt_items"
    __table_args__ = (
        db.UniqueConstraint("receipt_id", "order_item_id", name="uq_receipt_items_receipt_order_item"),
        db.Index("ix_receipt_items_tenant_receipt", "tenant_id", "receipt_id"),
        db.Index("ix_receipt_items_tenant_order_item", "tenant_id", "order_item_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = db.relationship("Tenant")
    receipt = db.relationship("Receipt", back_populates="items")
    order_item = db.relationship("OrderItem", back_populates="receipt_items")

    def to_dict(self):
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "order_item_id": self.order_item_id,
            "quantity": float(self.quantity),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
