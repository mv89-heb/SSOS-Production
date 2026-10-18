"""Store bounded supplier invoice attachments.

Revision ID: 20261022_supplier_invoice_files
Revises: 20261021_supplier_invoices
"""
from alembic import op
import sqlalchemy as sa

revision = "20261022_supplier_invoice_files"
down_revision = "20261021_supplier_invoices"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_invoices", sa.Column("attachment_filename", sa.String(length=255), nullable=True))
    op.add_column("supplier_invoices", sa.Column("attachment_mime_type", sa.String(length=100), nullable=True))
    op.add_column("supplier_invoices", sa.Column("attachment_size", sa.Integer(), nullable=True))
    op.add_column("supplier_invoices", sa.Column("attachment_data", sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column("supplier_invoices", "attachment_data")
    op.drop_column("supplier_invoices", "attachment_size")
    op.drop_column("supplier_invoices", "attachment_mime_type")
    op.drop_column("supplier_invoices", "attachment_filename")
