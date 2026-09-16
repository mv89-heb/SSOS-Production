from datetime import date, datetime, timezone

from app.extensions import db


class InventoryPlanningPeriod(db.Model):
    __tablename__ = "inventory_planning_periods"
    __table_args__ = (
        db.Index("ix_inventory_planning_periods_tenant_dates", "tenant_id", "start_date", "end_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    consumption_multiplier = db.Column(db.Numeric(8, 4), nullable=False, default=1.0)
    order_days = db.Column(db.String(100), nullable=True)
    delivery_days = db.Column(db.String(100), nullable=True)
    order_cutoff_time = db.Column(db.String(5), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = db.relationship("Tenant")
    creator = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "consumption_multiplier": float(self.consumption_multiplier or 1),
            "order_days": self.order_days or "",
            "delivery_days": self.delivery_days or "",
            "order_cutoff_time": self.order_cutoff_time,
            "active": self.active,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
