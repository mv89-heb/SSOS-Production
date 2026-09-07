"""supplier-aware order reminder rules

Revision ID: 20260906_supplier_reminders
Revises: 20260903_document_temp_path
"""
from alembic import op
import sqlalchemy as sa

revision = "20260906_supplier_reminders"
down_revision = "20260903_document_temp_path"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    return any(
        column["name"] == column_name
        for column in sa.inspect(bind).get_columns(table_name)
    )


def _index_exists(bind, table_name, index_name):
    return any(
        index["name"] == index_name
        for index in sa.inspect(bind).get_indexes(table_name)
    )


def upgrade():
    bind = op.get_bind()

    if not _column_exists(bind, "suppliers", "ordering_rules"):
        op.add_column(
            "suppliers", sa.Column("ordering_rules", sa.JSON(), nullable=True)
        )

    if not _column_exists(bind, "orders", "reminder_state"):
        op.add_column(
            "orders", sa.Column("reminder_state", sa.String(length=20), nullable=True)
        )

    if not _column_exists(bind, "orders", "reminder_rules_snapshot"):
        op.add_column(
            "orders",
            sa.Column("reminder_rules_snapshot", sa.JSON(), nullable=True),
        )

    if not _column_exists(bind, "orders", "next_reminder_at"):
        op.add_column(
            "orders", sa.Column("next_reminder_at", sa.DateTime(), nullable=True)
        )

    if not _index_exists(bind, "orders", "ix_orders_next_reminder_at"):
        op.create_index(
            "ix_orders_next_reminder_at",
            "orders",
            ["next_reminder_at"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()

    if _index_exists(bind, "orders", "ix_orders_next_reminder_at"):
        op.drop_index("ix_orders_next_reminder_at", table_name="orders")

    if _column_exists(bind, "orders", "next_reminder_at"):
        op.drop_column("orders", "next_reminder_at")

    if _column_exists(bind, "orders", "reminder_rules_snapshot"):
        op.drop_column("orders", "reminder_rules_snapshot")

    if _column_exists(bind, "orders", "reminder_state"):
        op.drop_column("orders", "reminder_state")

    if _column_exists(bind, "suppliers", "ordering_rules"):
        op.drop_column("suppliers", "ordering_rules")
