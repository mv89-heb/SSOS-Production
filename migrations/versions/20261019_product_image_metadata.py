"""Track product image source and last lookup time.

Revision ID: 20261019_product_image_metadata
Revises: 20261018_supplier_profile
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_product_image_metadata"
down_revision = "20261018_supplier_profile"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("products")}
    columns = [
        sa.Column("image_source", sa.String(80), nullable=True),
        sa.Column("image_source_url", sa.String(500), nullable=True),
        sa.Column("image_checked_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in columns:
        if column.name not in existing:
            op.add_column("products", column)


def downgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("products")}
    for name in ("image_checked_at", "image_source_url", "image_source"):
        if name in existing:
            op.drop_column("products", name)
