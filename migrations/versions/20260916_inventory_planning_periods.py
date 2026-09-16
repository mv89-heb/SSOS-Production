"""Add inventory planning periods for holiday demand and supplier schedule overrides.

Revision ID: 20260916_inventory_periods
Revises: 20260909_inventory_movements
"""
from alembic import op
import sqlalchemy as sa

revision = "20260916_inventory_periods"
down_revision = "20260909_inventory_movements"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return table_name in sa.inspect(bind).get_table_names()


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "inventory_planning_periods"):
        op.create_table(
            "inventory_planning_periods",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("consumption_multiplier", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("order_days", sa.String(length=100), nullable=True),
            sa.Column("delivery_days", sa.String(length=100), nullable=True),
            sa.Column("order_cutoff_time", sa.String(length=5), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists(bind, "inventory_planning_periods", "ix_inventory_planning_periods_tenant_dates"):
        op.create_index(
            "ix_inventory_planning_periods_tenant_dates",
            "inventory_planning_periods",
            ["tenant_id", "start_date", "end_date"],
            unique=False,
        )
    for name, columns in (
        ("ix_inventory_planning_periods_tenant", ["tenant_id"]),
        ("ix_inventory_planning_periods_created_by", ["created_by"]),
    ):
        if not _index_exists(bind, "inventory_planning_periods", name):
            op.create_index(name, "inventory_planning_periods", columns, unique=False)


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "inventory_planning_periods"):
        op.drop_table("inventory_planning_periods")
