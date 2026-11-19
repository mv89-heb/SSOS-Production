"""Protect procurement and price history from parent-record deletion.

Revision ID: 20261119_preserve_delete
Revises: 20261119_credit_adjustments
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_preserve_delete"
down_revision = "20261119_credit_adjustments"
branch_labels = None
depends_on = None

# These records are historical/business evidence. Parent deletion must be
# rejected by PostgreSQL even if a future code path forgets the service guard.
RESTRICTED_FOREIGN_KEYS = (
    ("supplier_invoices", "order_id", "orders"),
    ("order_tracking_events", "order_id", "orders"),
    ("price_history", "product_id", "products"),
    ("price_history", "supplier_id", "suppliers"),
    ("price_observations", "product_id", "products"),
    ("price_observations", "supplier_id", "suppliers"),
    ("product_codes", "product_id", "products"),
    ("product_classification_feedback", "product_id", "products"),
)


def _replace_foreign_key(table_name, column_name, referred_table, ondelete):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return

    matches = [
        fk for fk in inspector.get_foreign_keys(table_name)
        if fk.get("constrained_columns") == [column_name]
        and fk.get("referred_table") == referred_table
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one foreign key for {table_name}.{column_name}; found {len(matches)}"
        )

    existing = matches[0]
    current_ondelete = (existing.get("options") or {}).get("ondelete")
    if str(current_ondelete or "").upper() == ondelete:
        return
    constraint_name = existing.get("name")
    if not constraint_name:
        raise RuntimeError(f"Foreign key name is missing for {table_name}.{column_name}")

    op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    op.create_foreign_key(
        f"fk_{table_name}_{column_name}_{ondelete.lower()}",
        table_name,
        referred_table,
        [column_name],
        ["id"],
        ondelete=ondelete,
    )


def upgrade():
    for table_name, column_name, referred_table in RESTRICTED_FOREIGN_KEYS:
        _replace_foreign_key(table_name, column_name, referred_table, "RESTRICT")


def downgrade():
    for table_name, column_name, referred_table in RESTRICTED_FOREIGN_KEYS:
        _replace_foreign_key(table_name, column_name, referred_table, "CASCADE")
