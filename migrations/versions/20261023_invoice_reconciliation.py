"""Add supplier invoice line reconciliation.

Revision ID: 20261023_invoice_reconciliation
Revises: 20261022_supplier_invoice_files
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_invoice_reconciliation"
down_revision = "20261022_supplier_invoice_files"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_invoices", sa.Column("line_comparison", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("supplier_invoices", "line_comparison")
