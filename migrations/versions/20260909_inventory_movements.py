"""Add inventory movement ledger for demand-based replenishment.

Revision ID: 20260909_inventory_movements
Revises: 20260909_reminder_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_inventory_movements"
down_revision = "20260909_reminder_idempotency"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return table_name in sa.inspect(bind).get_table_names()


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "inventory_movements"):
        op.create_table(
            "inventory_movements",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("movement_type", sa.String(length=20), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
            sa.Column("balance_after", sa.Numeric(12, 3), nullable=True),
            sa.Column("reference_type", sa.String(length=50), nullable=True),
            sa.Column("reference_id", sa.String(length=100), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for name, columns in (
        ("ix_inventory_movements_tenant_product_date", ["tenant_id", "product_id", "occurred_at"]),
        ("ix_inventory_movements_tenant_type_date", ["tenant_id", "movement_type", "occurred_at"]),
    ):
        if not _index_exists(bind, "inventory_movements", name):
            op.create_index(name, "inventory_movements", columns, unique=False)
    for name, columns in (
        ("ix_inventory_movements_tenant", ["tenant_id"]),
        ("ix_inventory_movements_product", ["product_id"]),
        ("ix_inventory_movements_user", ["user_id"]),
        ("ix_inventory_movements_type", ["movement_type"]),
        ("ix_inventory_movements_occurred_at", ["occurred_at"]),
    ):
        if not _index_exists(bind, "inventory_movements", name):
            op.create_index(name, "inventory_movements", columns, unique=False)


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "inventory_movements"):
        op.drop_table("inventory_movements")
