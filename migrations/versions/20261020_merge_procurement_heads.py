"""Merge current mainline and procurement integrity migration heads.

Revision ID: 20261020_merge_procurement_heads
Revises: 20261019_product_image_metadata, 20260917_db_integrity
"""
revision = "20261020_merge_procurement_heads"
down_revision = ("20261019_product_image_metadata", "20260917_db_integrity")
branch_labels = None
depends_on = None


def upgrade():
    # Both parent branches have applied their own schema changes.
    pass


def downgrade():
    # Parent revisions are downgraded by Alembic after this merge node.
    pass
