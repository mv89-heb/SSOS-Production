"""add immutable supplier price observations

Revision ID: 20260901_price_observations
Revises: 20260901_price_intelligence
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_price_observations"
down_revision = "20260901_price_intelligence"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "price_observations" not in inspector.get_table_names():
        op.create_table(
            "price_observations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_document_id", sa.Integer(), nullable=True),
            sa.Column("observed_price", sa.Numeric(12, 4), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="ILS"),
            sa.Column("unit", sa.String(50), nullable=True),
            sa.Column("package_quantity", sa.Numeric(12, 4), nullable=True),
            sa.Column("comparison_unit", sa.String(20), nullable=True),
            sa.Column("price_basis", sa.String(20), nullable=False, server_default="NET"),
            sa.Column("source_type", sa.String(30), nullable=False, server_default="INVOICE"),
            sa.Column("match_method", sa.String(30), nullable=True),
            sa.Column("match_confidence", sa.Numeric(5, 4), nullable=True),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("price_observations")}
    for name, columns in {
        "ix_price_observations_tenant_id": ["tenant_id"],
        "ix_price_observations_product_id": ["product_id"],
        "ix_price_observations_supplier_id": ["supplier_id"],
        "ix_price_observation_tenant_product": ["tenant_id", "product_id"],
        "ix_price_observation_tenant_supplier": ["tenant_id", "supplier_id"],
        "ix_price_observation_document": ["tenant_id", "source_document_id"],
        "ix_price_observation_observed_at": ["tenant_id", "observed_at"],
    }.items():
        if name not in indexes:
            op.create_index(name, "price_observations", columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "price_observations" not in inspector.get_table_names():
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("price_observations")}
    for name in (
        "ix_price_observation_observed_at",
        "ix_price_observation_document",
        "ix_price_observation_tenant_supplier",
        "ix_price_observation_tenant_product",
        "ix_price_observations_supplier_id",
        "ix_price_observations_product_id",
        "ix_price_observations_tenant_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name="price_observations")
    op.drop_table("price_observations")
