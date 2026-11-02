"""Create official regulated egg price reference history.

Revision ID: 20261102_reg_egg_prices
Revises: 20261028_hist_doc_import
"""
from alembic import op
import sqlalchemy as sa
from datetime import date

revision = "20261102_reg_egg_prices"
down_revision = "20261028_hist_doc_import"
branch_labels = None
depends_on = None

SOURCE_URL = "https://www.gov.il/he/Departments/ministry_of_agriculture_and_food_security/govil-landing-page"
SOURCE_TITLE = "משרד החקלאות וביטחון המזון – עדכון מחירי ביצים בפיקוח"


def upgrade():
    op.create_table(
        "regulated_egg_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("size_code", sa.String(length=2), nullable=False),
        sa.Column("pack_size", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("max_consumer_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("change_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_title", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("effective_date", "size_code", name="uq_regulated_egg_price_effective_size"),
        sa.CheckConstraint("size_code IN ('M', 'L', 'XL')", name="ck_regulated_egg_price_size"),
        sa.CheckConstraint("max_consumer_price > 0", name="ck_regulated_egg_price_positive"),
    )
    op.create_index("ix_regulated_egg_price_effective", "regulated_egg_prices", ["effective_date"])

    op.create_table(
        "regulatory_price_monitor_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_article_url", sa.String(length=1000), nullable=True),
        sa.Column("last_article_title", sa.String(length=500), nullable=True),
        sa.Column("last_published_at", sa.String(length=30), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Official 12-egg consumer ceiling prices. Previous release is retained for
    # transparent history; this does not alter supplier offers or product prices.
    rows = [
        ("M", 13.13, date(2025, 11, 1), None, None),
        ("L", 14.24, date(2025, 11, 1), None, None),
        ("XL", 15.48, date(2025, 11, 1), None, None),
        ("M", 13.40, date(2026, 11, 1), date(2026, 10, 22), 2.1),
        ("L", 14.54, date(2026, 11, 1), date(2026, 10, 22), 2.1),
        ("XL", 15.81, date(2026, 11, 1), date(2026, 10, 22), 2.1),
    ]
    table = sa.table(
        "regulated_egg_prices",
        sa.column("size_code", sa.String),
        sa.column("pack_size", sa.Integer),
        sa.column("max_consumer_price", sa.Numeric(10, 2)),
        sa.column("effective_date", sa.Date),
        sa.column("published_at", sa.Date),
        sa.column("change_percent", sa.Numeric(6, 3)),
        sa.column("source_url", sa.String),
        sa.column("source_title", sa.String),
    )
    op.bulk_insert(table, [
        {
            "size_code": size, "pack_size": 12, "max_consumer_price": price,
            "effective_date": effective, "published_at": published,
            "change_percent": change, "source_url": SOURCE_URL,
            "source_title": SOURCE_TITLE,
        }
        for size, price, effective, published, change in rows
    ])


def downgrade():
    op.drop_table("regulatory_price_monitor_state")
    op.drop_index("ix_regulated_egg_price_effective", table_name="regulated_egg_prices")
    op.drop_table("regulated_egg_prices")
