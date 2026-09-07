"""Google Calendar integration persistence

Revision ID: 20260907_google_calendar
Revises: 20260906_supplier_reminders
"""
from alembic import op
import sqlalchemy as sa

revision = "20260907_google_calendar"
down_revision = "20260906_supplier_reminders"
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
    if not _column_exists(bind, "orders", "google_calendar_event_id"):
        op.add_column("orders", sa.Column("google_calendar_event_id", sa.String(length=255), nullable=True))
    if not _index_exists(bind, "orders", "ix_orders_google_calendar_event_id"):
        op.create_index("ix_orders_google_calendar_event_id", "orders", ["google_calendar_event_id"], unique=False)

    if not _table_exists(bind, "google_calendar_connections"):
        op.create_table(
            "google_calendar_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("google_email", sa.String(length=255), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
            sa.Column("calendar_id", sa.String(length=255), nullable=False, server_default="primary"),
            sa.Column("calendar_name", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "user_id", name="uq_google_calendar_tenant_user"),
        )
        op.create_index("ix_google_calendar_connections_tenant_id", "google_calendar_connections", ["tenant_id"], unique=False)
        op.create_index("ix_google_calendar_connections_user_id", "google_calendar_connections", ["user_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    if _table_exists(bind, "google_calendar_connections"):
        op.drop_index("ix_google_calendar_connections_user_id", table_name="google_calendar_connections")
        op.drop_index("ix_google_calendar_connections_tenant_id", table_name="google_calendar_connections")
        op.drop_table("google_calendar_connections")
    if _index_exists(bind, "orders", "ix_orders_google_calendar_event_id"):
        op.drop_index("ix_orders_google_calendar_event_id", table_name="orders")
    if _column_exists(bind, "orders", "google_calendar_event_id"):
        op.drop_column("orders", "google_calendar_event_id")
