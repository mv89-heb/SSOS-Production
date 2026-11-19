"""Add structured, auditable supplier credit adjustments.

Revision ID: 20261119_supplier_credit_adjustments
Revises: 20261119_saved_order_searches
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_supplier_credit_adjustments"
down_revision = "20261119_saved_order_searches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supplier_credit_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False),
        sa.Column("adjustment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("void_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "supplier_id", "reference_number",
            name="uq_supplier_credit_adjustment_reference",
        ),
        sa.CheckConstraint("amount > 0", name="ck_supplier_credit_adjustments_amount_positive"),
        sa.CheckConstraint(
            "adjustment_type IN ('credit_note', 'price_adjustment', 'goods_return')",
            name="ck_supplier_credit_adjustments_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'voided')",
            name="ck_supplier_credit_adjustments_status",
        ),
    )
    op.create_index(
        "ix_supplier_credit_adjustments_tenant_order_date",
        "supplier_credit_adjustments",
        ["tenant_id", "order_id", "adjustment_date"],
    )
    op.create_index(
        "ix_supplier_credit_adjustments_tenant_supplier_date",
        "supplier_credit_adjustments",
        ["tenant_id", "supplier_id", "adjustment_date"],
    )
    op.create_index(
        "ix_supplier_credit_adjustments_tenant_status",
        "supplier_credit_adjustments",
        ["tenant_id", "status"],
    )


def downgrade():
    op.drop_index("ix_supplier_credit_adjustments_tenant_status", table_name="supplier_credit_adjustments")
    op.drop_index("ix_supplier_credit_adjustments_tenant_supplier_date", table_name="supplier_credit_adjustments")
    op.drop_index("ix_supplier_credit_adjustments_tenant_order_date", table_name="supplier_credit_adjustments")
    op.drop_table("supplier_credit_adjustments")
