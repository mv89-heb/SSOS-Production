"""Add optional supplier contact, business, commercial and logistics profile fields.

Revision ID: 20261018_supplier_profile
Revises: 20261013_master_product_dedupe
"""
from alembic import op
import sqlalchemy as sa

revision = "20261018_supplier_profile"
down_revision = "20261013_master_product_dedupe"
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("tax_id", sa.String(100), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("supplier_category", sa.String(120), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("credit_days", sa.Integer(), nullable=True),
        sa.Column("minimum_order_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("delivery_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("order_cutoff_time", sa.String(20), nullable=True),
        sa.Column("certification_details", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    ]
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("suppliers")}
    for column in columns:
        if column.name not in existing:
            op.add_column("suppliers", column)


def downgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for name in [
        "notes", "certification_details", "order_cutoff_time", "lead_time_days",
        "delivery_fee", "minimum_order_amount", "credit_days", "payment_terms",
        "supplier_category", "website", "tax_id", "city", "address", "mobile",
    ]:
        if name in existing:
            op.drop_column("suppliers", name)
