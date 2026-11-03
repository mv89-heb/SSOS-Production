"""Add separate generated QR and barcode identifiers for products.

Revision ID: 20261028_product_codes
Revises: 20261028_hist_doc_import
"""
from alembic import op
import sqlalchemy as sa

revision = "20261028_product_codes"
down_revision = "20261028_hist_doc_import"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_type", sa.String(length=20), nullable=False),
        sa.Column("code_value", sa.String(length=1000), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code_value", name="uq_product_codes_tenant_value"),
        sa.UniqueConstraint("tenant_id", "product_id", "code_type", name="uq_product_codes_product_type"),
    )
    op.create_index("ix_product_codes_tenant_id", "product_codes", ["tenant_id"])
    op.create_index("ix_product_codes_tenant_product", "product_codes", ["tenant_id", "product_id"])


def downgrade():
    op.drop_index("ix_product_codes_tenant_product", table_name="product_codes")
    op.drop_index("ix_product_codes_tenant_id", table_name="product_codes")
    op.drop_table("product_codes")
