"""product classification metadata and feedback

Revision ID: 20260812_product_classification
Revises: 20260811_import_execution_integrity
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_product_classification"
down_revision = "20260811_import_execution_integrity"


def upgrade():
    op.add_column("products", sa.Column("category_source", sa.String(length=30), nullable=True))
    op.add_column("products", sa.Column("category_confidence", sa.Numeric(5, 4), nullable=True))
    op.add_column("products", sa.Column("category_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()))

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
    op.create_index("ix_product_classification_feedback_tenant_id", "product_classification_feedback", ["tenant_id"])
    op.create_index("ix_product_classification_feedback_product_id", "product_classification_feedback", ["product_id"])
    op.create_index("ix_product_classification_feedback_normalized_name", "product_classification_feedback", ["normalized_name"])


def downgrade():
    op.drop_index("ix_product_classification_feedback_normalized_name", table_name="product_classification_feedback")
    op.drop_index("ix_product_classification_feedback_product_id", table_name="product_classification_feedback")
    op.drop_index("ix_product_classification_feedback_tenant_id", table_name="product_classification_feedback")
    op.drop_table("product_classification_feedback")
    op.drop_column("products", "category_reviewed")
    op.drop_column("products", "category_confidence")
    op.drop_column("products", "category_source")
