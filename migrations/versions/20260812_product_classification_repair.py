"""repair product classification schema drift

The application model contains product classification metadata, but some
production databases may have reached an application revision without the
corresponding columns being present.  This migration is deliberately
idempotent so it can repair that drift without disturbing existing data.

Revision ID: 20260812_product_classification_repair
Revises: 20260812_product_classification
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_product_classification_repair"
down_revision = "20260812_product_classification"


def _column_exists(bind, table_name, column_name):
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()

    if not _column_exists(bind, "products", "category_source"):
        op.add_column("products", sa.Column("category_source", sa.String(length=30), nullable=True))

    if not _column_exists(bind, "products", "category_confidence"):
        op.add_column("products", sa.Column("category_confidence", sa.Numeric(5, 4), nullable=True))

    if not _column_exists(bind, "products", "category_reviewed"):
        op.add_column(
            "products",
            sa.Column(
                "category_reviewed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "product_classification_feedback" not in tables:
        op.create_table(
            "product_classification_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("normalized_name", sa.String(length=255), nullable=False),
            sa.Column("predicted_category", sa.String(length=100), nullable=True),
            sa.Column("actual_category", sa.String(length=100), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="USER"),
            sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    inspector = sa.inspect(bind)
    indexes = {
        index["name"]
        for index in inspector.get_indexes("product_classification_feedback")
    }

    if "ix_product_classification_feedback_tenant_id" not in indexes:
        op.create_index(
            "ix_product_classification_feedback_tenant_id",
            "product_classification_feedback",
            ["tenant_id"],
        )
    if "ix_product_classification_feedback_product_id" not in indexes:
        op.create_index(
            "ix_product_classification_feedback_product_id",
            "product_classification_feedback",
            ["product_id"],
        )
    if "ix_product_classification_feedback_normalized_name" not in indexes:
        op.create_index(
            "ix_product_classification_feedback_normalized_name",
            "product_classification_feedback",
            ["normalized_name"],
        )


def downgrade():
    # Do not remove repaired columns/table automatically.  This migration is
    # a production repair layer; destructive rollback belongs to the original
    # schema migration and must be explicit.
    pass
