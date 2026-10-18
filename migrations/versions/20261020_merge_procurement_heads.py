"""Merge current mainline and procurement integrity migration heads.

Revision ID: 20261020_merge_procurement_heads
Revises: 20261019_product_image_metadata, 20260917_db_integrity
"""
from alembic import op
import sqlalchemy as sa

revision = "20261020_merge_procurement_heads"
down_revision = ("20261019_product_image_metadata", "20260917_db_integrity")
branch_labels = None
depends_on = None


def upgrade():
    # Repair supplier schedule columns for databases that already recorded the
    # supplier-profile migration before its missing columns were corrected.
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for column in (
        sa.Column("phone2", sa.String(50), nullable=True),
        sa.Column("customer_number", sa.String(100), nullable=True),
        sa.Column("order_days", sa.String(100), nullable=True),
        sa.Column("delivery_days", sa.String(100), nullable=True),
        sa.Column("ordering_rules", sa.JSON(), nullable=True),
    ):
        if column.name not in existing:
            op.add_column("suppliers", column)
            existing.add(column.name)


def downgrade():
    # Parent revisions are downgraded by Alembic after this merge node.
    pass
