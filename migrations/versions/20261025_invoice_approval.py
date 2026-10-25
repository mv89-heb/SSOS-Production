"""Add supplier invoice approval workflow.

Revision ID: 20261025_invoice_approval
Revises: 20261023_invoice_reconciliation
"""
from alembic import op
import sqlalchemy as sa

revision = "20261025_invoice_approval"
down_revision = "20261023_invoice_reconciliation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "supplier_invoices",
        sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="pending_approval"),
    )
    op.add_column("supplier_invoices", sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("supplier_invoices", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("supplier_invoices", sa.Column("approval_note", sa.Text(), nullable=True))
    op.create_index("ix_supplier_invoices_approval_status", "supplier_invoices", ["approval_status"])


def downgrade():
    op.drop_index("ix_supplier_invoices_approval_status", table_name="supplier_invoices")
    op.drop_column("supplier_invoices", "approval_note")
    op.drop_column("supplier_invoices", "approved_at")
    op.drop_column("supplier_invoices", "approved_by")
    op.drop_column("supplier_invoices", "approval_status")
