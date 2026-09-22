"""Add planned order date for calendar-driven purchasing.

Revision ID: 20260922_planned_order_date
Revises: 20260916_inventory_periods
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_planned_order_date"
down_revision = "20260916_inventory_periods"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(bind).get_columns(table_name))


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    if not _column_exists(bind, "orders", "planned_order_date"):
        op.add_column("orders", sa.Column("planned_order_date", sa.Date(), nullable=True))
    if not _index_exists(bind, "orders", "ix_orders_tenant_planned_order_date"):
        op.create_index(
            "ix_orders_tenant_planned_order_date",
            "orders",
            ["tenant_id", "planned_order_date"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if _index_exists(bind, "orders", "ix_orders_tenant_planned_order_date"):
        op.drop_index("ix_orders_tenant_planned_order_date", table_name="orders")
    if _column_exists(bind, "orders", "planned_order_date"):
        op.drop_column("orders", "planned_order_date")
