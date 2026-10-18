"""Track last paid price per supplier offer.

Revision ID: 20261024_offer_last_paid
Revises: 20261023_invoice_reconciliation
"""
from alembic import op
import sqlalchemy as sa

revision = "20261024_offer_last_paid"
down_revision = "20261023_invoice_reconciliation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier_product_offers", sa.Column("last_paid_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("supplier_product_offers", sa.Column("last_paid_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("supplier_product_offers", "last_paid_at")
    op.drop_column("supplier_product_offers", "last_paid_price")
