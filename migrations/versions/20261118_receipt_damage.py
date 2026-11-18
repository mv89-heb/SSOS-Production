"""Track damaged quantity separately from accepted inventory quantity.

Revision ID: 20261118_receipt_damage
Revises: 20261028_product_codes, 20261102_reg_egg_prices
"""
from alembic import op
import sqlalchemy as sa

revision = "20261118_receipt_damage"
down_revision = ("20261028_product_codes", "20261102_reg_egg_prices")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "receipt_items",
        sa.Column("damaged_quantity", sa.Numeric(12, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "receipt_items",
        sa.Column("damage_notes", sa.String(length=1000), nullable=True),
    )


def downgrade():
    op.drop_column("receipt_items", "damage_notes")
    op.drop_column("receipt_items", "damaged_quantity")
