"""supplier-aware order reminder rules

Revision ID: 20260906_supplier_order_reminders
Revises: 20260903_document_temp_path
"""
from alembic import op
import sqlalchemy as sa

revision = "20260906_supplier_order_reminders"
down_revision = "20260903_document_temp_path"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suppliers", sa.Column("ordering_rules", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("reminder_state", sa.String(length=20), nullable=True))
    op.add_column("orders", sa.Column("reminder_rules_snapshot", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("next_reminder_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_orders_next_reminder_at",
        "orders",
        ["next_reminder_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_orders_next_reminder_at", table_name="orders")
    op.drop_column("orders", "next_reminder_at")
    op.drop_column("orders", "reminder_rules_snapshot")
    op.drop_column("orders", "reminder_state")
    op.drop_column("suppliers", "ordering_rules")
