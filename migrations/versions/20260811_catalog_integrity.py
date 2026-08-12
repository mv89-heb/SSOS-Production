"""catalog integrity constraints

Adds tenant-scoped uniqueness for product identifiers when existing data is
already clean. Legacy duplicate identifiers are preserved and reported rather
than aborting the entire deployment: the application already validates new
and edited SKU/barcode values, while the database constraint can be introduced
later after the legacy duplicates are resolved.

This migration intentionally continues from the production schema revision
20260720_preview_unit_cat. Production databases were observed at that
revision; keeping the migration graph linear ensures ``flask db upgrade`` can
advance them without creating a second Alembic head.

Revision ID: 20260811_catalog_integrity
Revises: 20260720_preview_unit_cat
Create Date: 2026-08-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260811_catalog_integrity"
down_revision = "20260720_preview_unit_cat"


def _duplicate_rows(bind, table, column):
    return bind.execute(
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


def _create_unique_index_if_clean(bind, index_name, column):
    duplicates = _duplicate_rows(bind, "products", column)
    if duplicates:
        examples = ", ".join(
            f"tenant={row[0]} {column}={row[1]!r} count={row[2]}"
            for row in duplicates[:5]
        )
        print(
            f"WARNING: skipping {index_name}; legacy duplicate {column} values exist: {examples}"
        )
        return False

    op.create_index(
        index_name,
        "products",
        ["tenant_id", column],
        unique=True,
        postgresql_where=sa.text(
            f"{column} IS NOT NULL AND btrim({column}) <> ''"
        ),
        sqlite_where=sa.text(
            f"{column} IS NOT NULL AND trim({column}) <> ''"
        ),
    )
    return True


def upgrade():
    bind = op.get_bind()
    _create_unique_index_if_clean(bind, "uq_products_tenant_sku", "sku")
    _create_unique_index_if_clean(bind, "uq_products_tenant_barcode", "barcode")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes("products")}

    if "uq_products_tenant_barcode" in existing:
        op.drop_index("uq_products_tenant_barcode", table_name="products")
    if "uq_products_tenant_sku" in existing:
        op.drop_index("uq_products_tenant_sku", table_name="products")
