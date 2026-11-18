from datetime import datetime, timezone

from app.extensions import db


class ProcurementBudget(db.Model):
    __tablename__ = "procurement_budgets"
    __table_args__ = (
        db.Index(
            "ix_procurement_budgets_scope_period",
            "tenant_id", "scope_type", "scope_value", "period_type", "period_start", "currency",
            unique=True,
        ),
        db.CheckConstraint("scope_type IN ('department', 'project')", name="ck_procurement_budgets_scope_type"),
        db.CheckConstraint("period_type IN ('weekly', 'monthly')", name="ck_procurement_budgets_period_type"),
        db.CheckConstraint("enforcement_mode IN ('warn', 'block')", name="ck_procurement_budgets_enforcement_mode"),
        db.CheckConstraint("amount > 0", name="ck_procurement_budgets_amount_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    scope_type = db.Column(db.String(20), nullable=False)
    scope_value = db.Column(db.String(120), nullable=False)
    period_type = db.Column(db.String(20), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS", server_default="ILS")
    enforcement_mode = db.Column(db.String(10), nullable=False, default="warn", server_default="warn")
    active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = db.relationship("Tenant")
    creator = db.relationship("User")

    def to_dict(self, spent_amount=None):
        amount = self.amount or 0
        spent = spent_amount
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "scope_type": self.scope_type,
            "scope_value": self.scope_value,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "amount": float(amount),
            "currency": self.currency,
            "enforcement_mode": self.enforcement_mode,
            "active": bool(self.active),
            "spent_amount": float(spent) if spent is not None else None,
            "remaining_amount": float(amount - spent) if spent is not None else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
