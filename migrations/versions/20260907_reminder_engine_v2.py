"""Reminder engine v2 persistence

Revision ID: 20260907_reminder_engine_v2
Revises: 20260907_google_calendar
"""
from alembic import op
import sqlalchemy as sa

revision = "20260907_reminder_engine_v2"
down_revision = "20260907_google_calendar"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(bind).get_columns(table_name))


def _table_exists(bind, table_name):
    return table_name in sa.inspect(bind).get_table_names()


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade():
    bind = op.get_bind()

    if not _column_exists(bind, "orders", "google_calendar_event_url"):
        op.add_column("orders", sa.Column("google_calendar_event_url", sa.Text(), nullable=True))

    if not _column_exists(bind, "notifications", "action_url"):
        op.add_column("notifications", sa.Column("action_url", sa.Text(), nullable=True))
    if not _column_exists(bind, "notifications", "notification_type"):
        op.add_column("notifications", sa.Column("notification_type", sa.String(length=50), nullable=True))

    if not _table_exists(bind, "web_push_subscriptions"):
        op.create_table(
            "web_push_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("p256dh", sa.Text(), nullable=False),
            sa.Column("auth", sa.Text(), nullable=False),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "endpoint", name="uq_web_push_user_endpoint"),
        )
        op.create_index("ix_web_push_subscriptions_tenant_id", "web_push_subscriptions", ["tenant_id"], unique=False)
        op.create_index("ix_web_push_subscriptions_user_id", "web_push_subscriptions", ["user_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "web_push_subscriptions"):
        op.drop_index("ix_web_push_subscriptions_user_id", table_name="web_push_subscriptions")
        op.drop_index("ix_web_push_subscriptions_tenant_id", table_name="web_push_subscriptions")
        op.drop_table("web_push_subscriptions")
    if _column_exists(bind, "notifications", "notification_type"):
        op.drop_column("notifications", "notification_type")
    if _column_exists(bind, "notifications", "action_url"):
        op.drop_column("notifications", "action_url")
    if _column_exists(bind, "orders", "google_calendar_event_url"):
        op.drop_column("orders", "google_calendar_event_url")
