from datetime import datetime, timezone

from app.extensions import db


class OrderItem(db.Model):
    """Operational purchase-order line.

    The legacy Order.items JSON remains as a compatibility snapshot during the
    migration. OrderItem is the source of truth for procurement quantities and
    receiving once the procurement flow is migrated.
    """

    __tablename__ = "order_items"
    __table_args__ = (
        db.Index("ix_order_items_tenant_order", "tenant_id", "order_id"),
        db.Index("ix_order_items_tenant_product", "tenant_id", "product_id"),
        db.Index("ix_order_items_tenant_offer", "tenant_id", "supplier_offer_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    supplier_offer_id = db.Column(db.Integer, db.ForeignKey("supplier_product_offers.id"), nullable=True, index=True)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    product_snapshot = db.Column(db.JSON, nullable=True)
    offer_snapshot = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = db.relationship("Tenant")
    order = db.relationship("Order", back_populates="order_items")
    product = db.relationship("Product")
    supplier_offer = db.relationship("SupplierProductOffer")
    receipt_items = db.relationship("ReceiptItem", back_populates="order_item", passive_deletes=True)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "supplier_offer_id": self.supplier_offer_id,
            "quantity": float(self.quantity),
            "unit_price": float(self.unit_price),
            "currency": self.currency,
            "product_snapshot": self.product_snapshot,
            "offer_snapshot": self.offer_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
