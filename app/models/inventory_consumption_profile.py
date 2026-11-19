from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db


class InventoryConsumptionProfile(db.Model):
    """Tenant-scoped planning profile; independent from physical stock and order history."""
    __tablename__ = "inventory_consumption_profiles"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "name", name="uq_inventory_consumption_profiles_tenant_name"),
        db.CheckConstraint("min_order_quantity >= 0", name="ck_inventory_consumption_profiles_min_order_nonnegative"),
        db.CheckConstraint("max_order_quantity >= min_order_quantity", name="ck_inventory_consumption_profiles_order_range"),
        db.CheckConstraint("average_order_quantity >= 0", name="ck_inventory_consumption_profiles_average_nonnegative"),
        db.CheckConstraint("regular_weekly_consumption >= 0", name="ck_inventory_consumption_profiles_regular_nonnegative"),
        db.CheckConstraint("reinforced_weekly_consumption >= 0", name="ck_inventory_consumption_profiles_reinforced_nonnegative"),
        db.CheckConstraint("reinforcement_cycle_weeks >= 1", name="ck_inventory_consumption_profiles_cycle_positive"),
        db.CheckConstraint("safety_stock >= 0", name="ck_inventory_consumption_profiles_safety_nonnegative"),
        db.Index("ix_inventory_consumption_profiles_tenant_active", "tenant_id", "active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    supplier_ids = db.Column(db.JSON, nullable=False, default=list)
    product_ids = db.Column(db.JSON, nullable=False, default=list)
    min_order_quantity = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    max_order_quantity = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    average_order_quantity = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    regular_weekly_consumption = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    reinforced_weekly_consumption = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    reinforcement_cycle_weeks = db.Column(db.Numeric(8, 3), nullable=False, default=3)
    safety_stock = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    order_status = db.Column(db.String(20), nullable=False, default="healthy")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    source_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @staticmethod
    def _number(value):
        return float(value or 0)

    @property
    def weighted_weekly_consumption(self):
        cycle = Decimal(str(self.reinforcement_cycle_weeks or 0))
        if cycle <= 0:
            return Decimal("0")
        regular = Decimal(str(self.regular_weekly_consumption or 0))
        reinforced = Decimal(str(self.reinforced_weekly_consumption or 0))
        return (regular * (cycle - 1) + reinforced) / cycle

    @property
    def monthly_consumption(self):
        # Keep the four-week planning month used by the supplied operating table.
        return self.weighted_weekly_consumption * Decimal("4")

    def to_dict(self, suppliers=None, products=None):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "supplier_ids": list(self.supplier_ids or []),
            "supplier_names": (suppliers or {}),
            "product_ids": list(self.product_ids or []),
            "product_names": (products or {}),
            "min_order_quantity": self._number(self.min_order_quantity),
            "max_order_quantity": self._number(self.max_order_quantity),
            "average_order_quantity": self._number(self.average_order_quantity),
            "regular_weekly_consumption": self._number(self.regular_weekly_consumption),
            "reinforced_weekly_consumption": self._number(self.reinforced_weekly_consumption),
            "reinforcement_cycle_weeks": self._number(self.reinforcement_cycle_weeks),
            "weighted_weekly_consumption": float(self.weighted_weekly_consumption),
            "monthly_consumption": float(self.monthly_consumption),
            "safety_stock": self._number(self.safety_stock),
            "order_status": self.order_status,
            "active": self.active,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source_note": self.source_note,
            "mapping_status": "mapped" if self.product_ids else "pending",
        }
