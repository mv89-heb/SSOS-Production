from datetime import datetime, timezone

from app.extensions import db


MOVEMENT_RECEIPT = "receipt"
MOVEMENT_ISSUE = "issue"
MOVEMENT_ADJUSTMENT = "adjustment"
MOVEMENT_COUNT = "count"
VALID_MOVEMENT_TYPES = (MOVEMENT_RECEIPT, MOVEMENT_ISSUE, MOVEMENT_ADJUSTMENT, MOVEMENT_COUNT)


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        db.Index("ix_inventory_movements_tenant_product_date", "tenant_id", "product_id", "occurred_at"),
        db.Index("ix_inventory_movements_tenant_type_date", "tenant_id", "movement_type", "occurred_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    movement_type = db.Column(db.String(20), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    balance_after = db.Column(db.Numeric(12, 3), nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    occurred_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    product = db.relationship("Product")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "movement_type": self.movement_type,
            "quantity": float(self.quantity),
            "balance_after": float(self.balance_after) if self.balance_after is not None else None,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "note": self.note,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
