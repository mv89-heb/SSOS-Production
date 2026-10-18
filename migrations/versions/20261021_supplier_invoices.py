"""Add supplier invoices and payment tracking.

Revision ID: 20261021_supplier_invoices
Revises: 20261020_merge_procurement_heads
"""
from alembic import op
import sqlalchemy as sa

revision = "20261021_supplier_invoices"
down_revision = "20261020_merge_procurement_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("receipts.id"), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("invoice_number", sa.String(length=120), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "supplier_id", "invoice_number", name="uq_supplier_invoice_number"),
    )
    op.create_index("ix_supplier_invoices_tenant_id", "supplier_invoices", ["tenant_id"])
    op.create_index("ix_supplier_invoices_order_id", "supplier_invoices", ["order_id"])
    op.create_index("ix_supplier_invoices_receipt_id", "supplier_invoices", ["receipt_id"])
    op.create_index("ix_supplier_invoices_supplier_id", "supplier_invoices", ["supplier_id"])
    op.create_index("ix_supplier_invoices_due_date", "supplier_invoices", ["due_date"])
    op.create_index("ix_supplier_invoices_tenant_order", "supplier_invoices", ["tenant_id", "order_id"])
    op.create_index("ix_supplier_invoices_tenant_due_date", "supplier_invoices", ["tenant_id", "due_date"])

    op.create_table(
        "supplier_invoice_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_invoice_payments_tenant_id", "supplier_invoice_payments", ["tenant_id"])
    op.create_index("ix_supplier_invoice_payments_invoice_id", "supplier_invoice_payments", ["invoice_id"])
    op.create_index("ix_supplier_invoice_payments_tenant_invoice", "supplier_invoice_payments", ["tenant_id", "invoice_id"])


def downgrade():
    op.drop_index("ix_supplier_invoice_payments_tenant_invoice", table_name="supplier_invoice_payments")
    op.drop_index("ix_supplier_invoice_payments_invoice_id", table_name="supplier_invoice_payments")
    op.drop_index("ix_supplier_invoice_payments_tenant_id", table_name="supplier_invoice_payments")
    op.drop_table("supplier_invoice_payments")
    op.drop_index("ix_supplier_invoices_tenant_due_date", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_tenant_order", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_due_date", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_supplier_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_receipt_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_order_id", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_tenant_id", table_name="supplier_invoices")
    op.drop_table("supplier_invoices")
