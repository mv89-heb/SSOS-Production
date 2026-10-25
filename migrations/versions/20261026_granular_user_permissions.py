"""Add per-user granular permission overrides.

Revision ID: 20261026_user_perms
Revises: 20261025_invoice_approval, 20261025_order_tracking
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_user_perms"
down_revision = ("20261025_invoice_approval", "20261025_order_tracking")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("permissions", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("users", "permissions")
