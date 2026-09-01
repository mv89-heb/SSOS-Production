"""price intelligence history

Revision ID: 20260901_price_intelligence
Revises: 20260812_product_classification_repair
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_price_intelligence"
down_revision = "20260812_product_classification_repair"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "price_history" not in inspector.get_table_names():
        op.create_table(
            "price_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("old_price", sa.Numeric(12, 2), nullable=True),
            sa.Column("new_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
            sa.Column("unit", sa.String(length=50), nullable=True),
            sa.Column("source_type", sa.String(length=30), nullable=False, server_default="MANUAL"),
            sa.Column("source_document_id", sa.Integer(), nullable=True),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("change_percent", sa.Numeric(10, 4), nullable=True),
        )

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("price_history")}
    for name, columns in {
        "ix_price_history_tenant_id": ["tenant_id"],
        "ix_price_history_product_id": ["product_id"],
        "ix_price_history_supplier_id": ["supplier_id"],
        "ix_price_history_effective_at": ["tenant_id", "effective_at"],
        "ix_price_history_tenant_product": ["tenant_id", "product_id"],
        "ix_price_history_tenant_supplier": ["tenant_id", "supplier_id"],
    }.items():
        if name not in indexes:
            op.create_index(name, "price_history", columns)


def downgrade():
    op.drop_index("ix_price_history_tenant_supplier", table_name="price_history")
    op.drop_index("ix_price_history_tenant_product", table_name="price_history")
    op.drop_index("ix_price_history_effective_at", table_name="price_history")
    op.drop_index("ix_price_history_supplier_id", table_name="price_history")
    op.drop_index("ix_price_history_product_id", table_name="price_history")
    op.drop_index("ix_price_history_tenant_id", table_name="price_history")
    op.drop_table("price_history")
