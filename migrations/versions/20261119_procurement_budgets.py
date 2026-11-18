"""Add tenant-scoped procurement budgets and order cost centers.

Revision ID: 20261119_procurement_budgets
Revises: 20261118_receipt_damage
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_procurement_budgets"
down_revision = "20261118_receipt_damage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("department", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("project", sa.String(length=120), nullable=True))
    op.create_table(
        "procurement_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_value", sa.String(length=120), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
        sa.Column("enforcement_mode", sa.String(length=10), nullable=False, server_default="warn"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("scope_type IN ('department', 'project')", name="ck_procurement_budgets_scope_type"),
        sa.CheckConstraint("period_type IN ('weekly', 'monthly')", name="ck_procurement_budgets_period_type"),
        sa.CheckConstraint("enforcement_mode IN ('warn', 'block')", name="ck_procurement_budgets_enforcement_mode"),
        sa.CheckConstraint("amount > 0", name="ck_procurement_budgets_amount_positive"),
    )
    op.create_index(
        "ix_procurement_budgets_scope_period",
        "procurement_budgets",
        ["tenant_id", "scope_type", "scope_value", "period_type", "period_start", "currency"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_procurement_budgets_scope_period", table_name="procurement_budgets")
    op.drop_table("procurement_budgets")
    op.drop_column("orders", "project")
    op.drop_column("orders", "department")
