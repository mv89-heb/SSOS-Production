"""catalog integrity constraints

Adds tenant-scoped uniqueness for the two product identifiers that are
already treated as identifiers by the application:

* Product.sku — unique within a tenant when present.
* Product.barcode — unique within a tenant when present.

NULL remains allowed, so products without an identifier are unaffected.
The migration deliberately fails before creating the indexes when existing
data contains duplicates; this prevents silently changing or deleting
catalog data during deployment.

Revision ID: 20260811_catalog_integrity
Revises: 20260720_import_execution
Create Date: 2026-08-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260811_catalog_integrity"
down_revision = "20260720_import_execution"


def _assert_no_duplicates(bind, table, column, label):
    rows = bind.execute(
        sa.text(
            f"""
            SELECT tenant_id, {column}, COUNT(*) AS duplicate_count
            FROM {table}
            WHERE {column} IS NOT NULL AND TRIM({column}) <> ''
            GROUP BY tenant_id, {column}
            HAVING COUNT(*) > 1
            ORDER BY tenant_id, {column}
            LIMIT 20
            """
        )
    ).fetchall()
    if rows:
        examples = ", ".join(
            f"tenant={row[0]} {column}={row[1]!r} count={row[2]}"
            for row in rows
        )
        raise RuntimeError(
            f"Cannot apply {label} uniqueness constraint: duplicate values "
            f"already exist. Resolve the duplicates first. Examples: {examples}"
        )


def upgrade():
    bind = op.get_bind()

    _assert_no_duplicates(bind, "products", "sku", "SKU")
    _assert_no_duplicates(bind, "products", "barcode", "barcode")

    # Partial indexes make the intended rule explicit: blank/NULL identifiers
    # are not treated as identifiers, while real identifiers are unique per
    # tenant. PostgreSQL and SQLite both support partial indexes.
    op.create_index(
        "uq_products_tenant_sku",
        "products",
        ["tenant_id", "sku"],
        unique=True,
        postgresql_where=sa.text("sku IS NOT NULL AND btrim(sku) <> ''"),
        sqlite_where=sa.text("sku IS NOT NULL AND trim(sku) <> ''"),
    )
    op.create_index(
        "uq_products_tenant_barcode",
        "products",
        ["tenant_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL AND btrim(barcode) <> ''"),
        sqlite_where=sa.text("barcode IS NOT NULL AND trim(barcode) <> ''"),
    )


def downgrade():
    op.drop_index("uq_products_tenant_barcode", table_name="products")
    op.drop_index("uq_products_tenant_sku", table_name="products")
