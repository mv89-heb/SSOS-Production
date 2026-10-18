"""Add optional supplier profile fields and backfill known delivery schedules.

Revision ID: 20261018_supplier_profile
Revises: 20261013_master_product_dedupe, 95371bcfb9b2
"""
from alembic import op
import sqlalchemy as sa

revision = "20261018_supplier_profile"
down_revision = ("20261013_master_product_dedupe", "95371bcfb9b2")
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
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for column in columns:
        if column.name not in existing:
            op.add_column("suppliers", column)

    # Populate only empty values from the repository's maintained supplier
    # schedule master. Existing manually maintained schedules are preserved.
    suppliers = sa.table(
        "suppliers",
        sa.column("name", sa.String),
        sa.column("order_days", sa.String),
        sa.column("delivery_days", sa.String),
        sa.column("supplier_category", sa.String),
    )
    schedule_rows = [
        (("אנג'ל", "אנג'ל בית מאפה"), "מאפה", "ראשון, שני, שלישי, רביעי, חמישי, שישי", "ראשון, שני, שלישי, רביעי, חמישי, שישי"),
        (("תנובה",), "מוצרי חלב", "ראשון, שלישי, חמישי", "שני, רביעי, שישי"),
        (("אוסם",), "יבש וקפוא", "שני, רביעי", "שלישי, חמישי"),
        (("ווגשל",), "מזון", "ראשון, רביעי", "שני, חמישי"),
        (("טמפו",), "משקאות", "שני", "שלישי"),
        (("גידרון",), "קפואים", "ראשון, שלישי", "שני, רביעי"),
        (("בן אנד ג'רי", "בן ג'ריס", "בנז'ריס", "בן אן ג'ריס"), "גלידות", "שני", "שלישי"),
        (("עמית",), "מזון", "ראשון, רביעי", "שני, חמישי"),
    ]
    for names, category, order_days, delivery_days in schedule_rows:
        for name in names:
            bind.execute(
                suppliers.update()
                .where(sa.func.lower(sa.func.trim(suppliers.c.name)) == name.lower())
                .values(
                    supplier_category=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.supplier_category), ""), category),
                    order_days=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.order_days), ""), order_days),
                    delivery_days=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.delivery_days), ""), delivery_days),
                )
            )


def downgrade():
    # The schedule backfill intentionally remains: deleting newly learned
    # supplier data during rollback would be surprising and irreversible.
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for name in [
        "notes", "certification_details", "order_cutoff_time", "lead_time_days",
        "delivery_fee", "minimum_order_amount", "credit_days", "payment_terms",
        "supplier_category", "website", "tax_id", "city", "address", "mobile",
    ]:
        if name in existing:
            op.drop_column("suppliers", name)
