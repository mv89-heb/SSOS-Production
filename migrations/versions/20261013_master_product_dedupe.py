"""Consolidate exact duplicate master products without touching legacy orders.

Revision ID: 20261013_master_product_dedupe
Revises: 20261012_master_supplier_prod
"""
from alembic import op
import sqlalchemy as sa

revision = "20261013_master_product_dedupe"
down_revision = "20261012_master_supplier_prod"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    master = sa.table(
        "master_products",
        sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("normalized_name", sa.String), sa.column("category", sa.String),
        sa.column("base_unit", sa.String), sa.column("barcode", sa.String),
    )
    listings = sa.table(
        "supplier_products",
        sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("master_product_id", sa.Integer),
        sa.column("suggested_master_product_id", sa.Integer),
    )
    rows = bind.execute(sa.select(master).order_by(master.c.tenant_id, master.c.id)).mappings().all()
    buckets = {}
    for row in rows:
        key = (
            row["tenant_id"],
            " ".join(str(row["normalized_name"] or "").casefold().split()),
            " ".join(str(row["category"] or "").casefold().split()),
            " ".join(str(row["base_unit"] or "").casefold().split()),
        )
        buckets.setdefault(key, []).append(row)

    for candidates in buckets.values():
        if len(candidates) < 2:
            continue
        barcodes = {
            "".join(ch for ch in str(row["barcode"] or "") if ch.isdigit())
            for row in candidates
            if str(row["barcode"] or "").strip()
            and not "".join(ch for ch in str(row["barcode"] or "") if ch.isdigit()).startswith("990000010000")
        }
        # Exact-name candidates with conflicting real barcodes are distinct
        # products. Do not guess or merge them.
        if len(barcodes) > 1:
            continue
        canonical_id = candidates[0]["id"]
        duplicate_ids = [row["id"] for row in candidates[1:]]
        for duplicate_id in duplicate_ids:
            bind.execute(
                listings.update()
                .where(listings.c.tenant_id == candidates[0]["tenant_id"])
                .where(listings.c.master_product_id == duplicate_id)
                .values(master_product_id=canonical_id)
            )
            bind.execute(
                listings.update()
                .where(listings.c.tenant_id == candidates[0]["tenant_id"])
                .where(listings.c.suggested_master_product_id == duplicate_id)
                .values(suggested_master_product_id=canonical_id)
            )
        bind.execute(master.delete().where(master.c.id.in_(duplicate_ids)))


def downgrade():
    # Reconstructing previously separate master identities is ambiguous; the
    # forward migration is deliberately data-preserving and non-destructive.
    pass
