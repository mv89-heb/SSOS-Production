from datetime import datetime, timezone

from app.extensions import db


CREDIT_ADJUSTMENT_CREDIT_NOTE = "credit_note"
CREDIT_ADJUSTMENT_PRICE_ADJUSTMENT = "price_adjustment"
CREDIT_ADJUSTMENT_GOODS_RETURN = "goods_return"
VALID_CREDIT_ADJUSTMENT_TYPES = (
    CREDIT_ADJUSTMENT_CREDIT_NOTE,
    CREDIT_ADJUSTMENT_PRICE_ADJUSTMENT,
    CREDIT_ADJUSTMENT_GOODS_RETURN,
)
CREDIT_ADJUSTMENT_ACTIVE = "active"
CREDIT_ADJUSTMENT_VOIDED = "voided"


class SupplierCreditAdjustment(db.Model):
    """Append-only supplier credit/adjustment record linked to its purchase order."""
    __tablename__ = "supplier_credit_adjustments"
    __table_args__ = (
        db.UniqueConstraint(
            "tenant_id", "supplier_id", "reference_number",
            name="uq_supplier_credit_adjustment_reference",
        ),
        db.Index(
            "ix_supplier_credit_adjustments_tenant_order_date",
            "tenant_id", "order_id", "adjustment_date",
        ),
        db.Index(
            "ix_supplier_credit_adjustments_tenant_supplier_date",
            "tenant_id", "supplier_id", "adjustment_date",
        ),
        db.CheckConstraint("amount > 0", name="ck_supplier_credit_adjustments_amount_positive"),
        db.CheckConstraint(
            "adjustment_type IN ('credit_note', 'price_adjustment', 'goods_return')",
            name="ck_supplier_credit_adjustments_type",
        ),
        db.CheckConstraint(
            "status IN ('active', 'voided')",
            name="ck_supplier_credit_adjustments_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("supplier_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    reference_number = db.Column(db.String(120), nullable=False)
    adjustment_type = db.Column(db.String(32), nullable=False)
    adjustment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default=CREDIT_ADJUSTMENT_ACTIVE)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    voided_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    void_reason = db.Column(db.String(1000), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    order = db.relationship("Order")
    invoice = db.relationship("SupplierInvoice")
    supplier = db.relationship("Supplier")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "invoice_id": self.invoice_id,
            "supplier_id": self.supplier_id,
            "reference_number": self.reference_number,
            "adjustment_type": self.adjustment_type,
            "adjustment_date": self.adjustment_date.isoformat() if self.adjustment_date else None,
            "amount": float(self.amount),
            "currency": self.currency,
            "reason": self.reason,
            "status": self.status,
            "voided_at": self.voided_at.isoformat() if self.voided_at else None,
            "voided_by": self.voided_by,
            "void_reason": self.void_reason,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
