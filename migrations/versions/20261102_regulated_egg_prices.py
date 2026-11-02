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

OFFICIAL_2025_URL = "https://www.gov.il/BlobFolder/guide/egg_price_years/he/investment_publication_order_price_2025_signed.pdf"
ANNOUNCEMENT_2026_URL = "https://www.gov.il/he/Departments/ministry_of_agriculture_and_food_security/govil-landing-page"
SOURCE_TITLE_2025 = "הודעת פיקוח – מחירים מרביים לביצי מאכל, 1.11.2025"
SOURCE_TITLE_2026 = "משרד החקלאות – הודעה על עדכון מחירי ביצים ב-2.1%, 22.10.2026"


def upgrade():
    op.create_table(
        "regulated_egg_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("size_code", sa.String(length=2), nullable=False),
        sa.Column("pack_size", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("max_consumer_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="OFFICIAL"),
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
        ("M", 13.13, date(2025, 11, 1), None, None, "OFFICIAL", OFFICIAL_2025_URL, SOURCE_TITLE_2025),
        ("L", 14.24, date(2025, 11, 1), None, None, "OFFICIAL", OFFICIAL_2025_URL, SOURCE_TITLE_2025),
        ("XL", 15.48, date(2025, 11, 1), None, None, "OFFICIAL", OFFICIAL_2025_URL, SOURCE_TITLE_2025),
        ("M", None, date(2026, 11, 1), date(2026, 10, 22), 2.1, "ANNOUNCED_RATE_ONLY", ANNOUNCEMENT_2026_URL, SOURCE_TITLE_2026),
        ("L", None, date(2026, 11, 1), date(2026, 10, 22), 2.1, "ANNOUNCED_RATE_ONLY", ANNOUNCEMENT_2026_URL, SOURCE_TITLE_2026),
        ("XL", None, date(2026, 11, 1), date(2026, 10, 22), 2.1, "ANNOUNCED_RATE_ONLY", ANNOUNCEMENT_2026_URL, SOURCE_TITLE_2026),
    ]
    table = sa.table(
        "regulated_egg_prices",
        sa.column("size_code", sa.String),
        sa.column("pack_size", sa.Integer),
        sa.column("max_consumer_price", sa.Numeric(10, 2)),
        sa.column("verification_status", sa.String),
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
            "change_percent": change, "verification_status": verification_status, "source_url": source_url,
            "source_title": source_title,
        }
        for size, price, effective, published, change, verification_status, source_url, source_title in rows
    ])


def downgrade():
    op.drop_table("regulatory_price_monitor_state")
    op.drop_index("ix_regulated_egg_price_effective", table_name="regulated_egg_prices")
    op.drop_table("regulated_egg_prices")
