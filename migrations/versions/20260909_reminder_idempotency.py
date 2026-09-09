"""Add durable reminder occurrence idempotency.

Revision ID: 20260909_reminder_idempotency
Revises: 20260907_reminder_engine_v2
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_reminder_idempotency"
down_revision = "20260907_reminder_engine_v2"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(bind).get_columns(table_name))


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    if not _column_exists(bind, "notifications", "dedupe_key"):
        op.add_column("notifications", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    if not _index_exists(bind, "notifications", "uq_notifications_dedupe_key"):
        op.create_index("uq_notifications_dedupe_key", "notifications", ["dedupe_key"], unique=True)


def downgrade():
    bind = op.get_bind()
    if _index_exists(bind, "notifications", "uq_notifications_dedupe_key"):
        op.drop_index("uq_notifications_dedupe_key", table_name="notifications")
    if _column_exists(bind, "notifications", "dedupe_key"):
        op.drop_column("notifications", "dedupe_key")
