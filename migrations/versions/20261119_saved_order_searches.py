"""Add private tenant-scoped saved order searches.

Revision ID: 20261119_saved_order_searches
Revises: 20261119_procurement_budgets
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_saved_order_searches"
down_revision = "20261119_procurement_budgets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_order_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "name", name="uq_saved_order_searches_tenant_user_name"),
        sa.CheckConstraint("length(name) > 0", name="ck_saved_order_searches_name_nonempty"),
    )
    op.create_index(
        "ix_saved_order_searches_tenant_user_updated",
        "saved_order_searches",
        ["tenant_id", "user_id", "updated_at"],
    )


def downgrade():
    op.drop_index("ix_saved_order_searches_tenant_user_updated", table_name="saved_order_searches")
    op.drop_table("saved_order_searches")
