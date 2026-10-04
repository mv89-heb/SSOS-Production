"""Add provenance fields for Gemini web price completion.

Revision ID: 20261004_gemini_price_completion
Revises: 20260922_planned_order_date
"""
from alembic import op
import sqlalchemy as sa

revision = "20261004_gemini_price_completion"
down_revision = "20260922_planned_order_date"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name, column_name):
    return any(c["name"] == column_name for c in sa.inspect(bind).get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    for name, column in [
        ("source_url", sa.String(length=1000)),
        ("source_title", sa.String(length=300)),
        ("match_method", sa.String(length=50)),
        ("match_confidence", sa.Numeric(5, 4)),
    ]:
        if not _column_exists(bind, "price_history", name):
            op.add_column("price_history", sa.Column(name, column, nullable=True))


def downgrade():
    bind = op.get_bind()
    for name in ("match_confidence", "match_method", "source_title", "source_url"):
        if _column_exists(bind, "price_history", name):
            op.drop_column("price_history", name)
