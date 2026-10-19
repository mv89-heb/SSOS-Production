"""Add internal order tracking events.

Revision ID: 20261025_order_tracking
Revises: 20261024_offer_last_paid
"""
from alembic import op
import sqlalchemy as sa

revision = "20261025_order_tracking"
down_revision = "20261024_offer_last_paid"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_tracking_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_tracking_events_tenant_id", "order_tracking_events", ["tenant_id"])
    op.create_index("ix_order_tracking_events_order_id", "order_tracking_events", ["order_id"])
    op.create_index("ix_order_tracking_tenant_order_time", "order_tracking_events", ["tenant_id", "order_id", "occurred_at"])
    op.create_index("ix_order_tracking_tenant_followup", "order_tracking_events", ["tenant_id", "next_follow_up_at"])


def downgrade():
    op.drop_index("ix_order_tracking_tenant_followup", table_name="order_tracking_events")
    op.drop_index("ix_order_tracking_tenant_order_time", table_name="order_tracking_events")
    op.drop_index("ix_order_tracking_events_order_id", table_name="order_tracking_events")
    op.drop_index("ix_order_tracking_events_tenant_id", table_name="order_tracking_events")
    op.drop_table("order_tracking_events")
