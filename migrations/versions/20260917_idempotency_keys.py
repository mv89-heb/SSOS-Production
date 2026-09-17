"""Add tenant-scoped idempotency keys for critical mutations.

Revision ID: 20260917_idempotency_keys
Revises: 20260916_inventory_periods
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_idempotency_keys"
down_revision = "20260916_inventory_periods"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return table_name in sa.inspect(bind).get_table_names()


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "idempotency_keys"):
        op.create_table(
            "idempotency_keys",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("request_hash", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=50), nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("response_status", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
        )
    if not _index_exists(bind, "idempotency_keys", "ix_idempotency_keys_tenant"):
        op.create_index("ix_idempotency_keys_tenant", "idempotency_keys", ["tenant_id"], unique=False)
    if not _index_exists(bind, "idempotency_keys", "ix_idempotency_keys_user"):
        op.create_index("ix_idempotency_keys_user", "idempotency_keys", ["user_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "idempotency_keys"):
        op.drop_table("idempotency_keys")
