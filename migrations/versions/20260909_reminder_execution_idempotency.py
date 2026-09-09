"""Add durable reminder execution idempotency metadata.

Revision ID: 20260909_reminder_execution_idempotency
Revises: 
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_reminder_execution_idempotency"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "reminder_occurrence" not in columns:
        op.add_column("orders", sa.Column("reminder_occurrence", sa.Integer(), nullable=False, server_default="0"))
    indexes = {index["name"] for index in inspector.get_indexes("orders")}
    if "ix_orders_reminder_execution" not in indexes:
        op.create_index(
            "ix_orders_reminder_execution",
            "orders",
            ["id", "next_reminder_at", "reminder_occurrence"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("orders")}
    if "ix_orders_reminder_execution" in indexes:
        op.drop_index("ix_orders_reminder_execution", table_name="orders")
    columns = {column["name"] for column in inspector.get_columns("orders")}
    if "reminder_occurrence" in columns:
        op.drop_column("orders", "reminder_occurrence")
