from datetime import datetime, timezone

from app.extensions import db


class SupplierInvoice(db.Model):
    """Tenant-scoped supplier invoice linked to a purchase order and optionally a receipt."""
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "supplier_id", "invoice_number", name="uq_supplier_invoice_number"),
        db.Index("ix_supplier_invoices_tenant_order", "tenant_id", "order_id"),
        db.Index("ix_supplier_invoices_tenant_due_date", "tenant_id", "due_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("receipts.id"), nullable=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    invoice_number = db.Column(db.String(120), nullable=False)
    invoice_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    notes = db.Column(db.Text, nullable=True)
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_mime_type = db.Column(db.String(100), nullable=True)
    attachment_size = db.Column(db.Integer, nullable=True)
    attachment_data = db.Column(db.LargeBinary, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    order = db.relationship("Order")
    supplier = db.relationship("Supplier")
    receipt = db.relationship("Receipt")
    payments = db.relationship("SupplierInvoicePayment", back_populates="invoice", cascade="all, delete-orphan", order_by="SupplierInvoicePayment.payment_date, SupplierInvoicePayment.id")

    @property
    def paid_amount(self):
        return sum((payment.amount for payment in self.payments), start=0)

    def to_dict(self):
        paid = sum((float(payment.amount) for payment in self.payments), 0.0)
        amount = float(self.amount)
        return {
            "id": self.id, "order_id": self.order_id, "receipt_id": self.receipt_id,
            "supplier_id": self.supplier_id, "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "amount": amount, "paid_amount": paid, "balance": round(amount - paid, 2),
            "currency": self.currency, "status": "paid" if paid >= amount else ("partially_paid" if paid > 0 else "unpaid"),
            "notes": self.notes, "attachment_filename": self.attachment_filename, "attachment_mime_type": self.attachment_mime_type, "attachment_size": self.attachment_size, "created_at": self.created_at.isoformat() if self.created_at else None,
            "payments": [payment.to_dict() for payment in self.payments],
        }


class SupplierInvoicePayment(db.Model):
    __tablename__ = "supplier_invoice_payments"
    __table_args__ = (db.Index("ix_supplier_invoice_payments_tenant_invoice", "tenant_id", "invoice_id"),)

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    reference = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = db.relationship("SupplierInvoice", back_populates="payments")

    def to_dict(self):
        return {
            "id": self.id, "invoice_id": self.invoice_id, "amount": float(self.amount),
            "payment_date": self.payment_date.isoformat(), "reference": self.reference,
            "notes": self.notes, "created_at": self.created_at.isoformat() if self.created_at else None,
        }
