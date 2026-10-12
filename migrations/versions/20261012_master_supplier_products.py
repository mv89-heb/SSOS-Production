"""Add canonical master products and supplier-specific product listings.

Revision ID: 20261012_master_supplier_products
Revises: 20261004_gemini_price_completion
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012_master_supplier_products"
down_revision = "20261004_gemini_price_completion"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "master_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(512), nullable=False),
        sa.Column("brand", sa.String(120)),
        sa.Column("category", sa.String(100)),
        sa.Column("barcode", sa.String(64)),
        sa.Column("base_unit", sa.String(30)),
        sa.Column("package_size", sa.Numeric(12, 4)),
        sa.Column("package_unit", sa.String(30)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_master_products_tenant_id_id"),
    )
    op.create_index("ix_master_products_tenant_id", "master_products", ["tenant_id"])
    op.create_index("ix_master_products_tenant_normalized_name", "master_products", ["tenant_id", "normalized_name"])

    op.create_table(
        "supplier_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("master_product_id", sa.Integer(), sa.ForeignKey("master_products.id")),
        sa.Column("suggested_master_product_id", sa.Integer(), sa.ForeignKey("master_products.id")),
        sa.Column("supplier_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("supplier_sku", sa.String(120)),
        sa.Column("barcode", sa.String(64)),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ILS"),
        sa.Column("unit", sa.String(50)),
        sa.Column("units_per_carton", sa.Integer()),
        sa.Column("normalized_name", sa.String(512), nullable=False, server_default=""),
        sa.Column("match_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("match_confidence", sa.Numeric(5, 4)),
        sa.Column("match_method", sa.String(40)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_supplier_products_tenant_id_id"),
        sa.CheckConstraint("price IS NULL OR price > 0", name="ck_supplier_products_positive_price"),
        sa.CheckConstraint("match_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_supplier_products_match_status"),
    )
    op.create_index("ix_supplier_products_tenant_id", "supplier_products", ["tenant_id"])
    op.create_index("ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"])
    op.create_index("ix_supplier_products_master_product_id", "supplier_products", ["master_product_id"])
    op.create_index("ix_supplier_products_tenant_supplier", "supplier_products", ["tenant_id", "supplier_id"])
    op.create_index("ix_supplier_products_tenant_master", "supplier_products", ["tenant_id", "master_product_id"])
    # Legacy data may contain duplicate supplier SKUs; index for lookup without
    # making a historic migration fail or silently dropping catalog rows.
    op.create_index(
        "ix_supplier_products_tenant_supplier_sku",
        "supplier_products", ["tenant_id", "supplier_id", "supplier_sku"],
        unique=False,
    )

    # Backfill conservatively: each legacy catalog product becomes its own master
    # product. No fuzzy merge is performed during a schema migration.
    bind = op.get_bind()
    products = sa.table(
        "products",
        sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("supplier_id", sa.Integer), sa.column("name", sa.String),
        sa.column("description", sa.Text), sa.column("sku", sa.String),
        sa.column("supplier_sku", sa.String), sa.column("barcode", sa.String),
        sa.column("current_price", sa.Numeric), sa.column("currency", sa.String),
        sa.column("unit", sa.String), sa.column("units_per_carton", sa.Integer),
        sa.column("category", sa.String), sa.column("active", sa.Boolean),
    )
    suppliers = sa.table(
        "suppliers", sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("name", sa.String),
    )
    master = sa.table(
        "master_products",
        sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer),
        sa.column("canonical_name", sa.String), sa.column("normalized_name", sa.String),
        sa.column("category", sa.String), sa.column("barcode", sa.String),
        sa.column("base_unit", sa.String), sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    supplier_product = sa.table(
        "supplier_products",
        sa.column("tenant_id", sa.Integer), sa.column("supplier_id", sa.Integer),
        sa.column("master_product_id", sa.Integer), sa.column("supplier_name", sa.String),
        sa.column("description", sa.Text), sa.column("supplier_sku", sa.String),
        sa.column("barcode", sa.String), sa.column("price", sa.Numeric),
        sa.column("currency", sa.String), sa.column("unit", sa.String),
        sa.column("units_per_carton", sa.Integer), sa.column("normalized_name", sa.String),
        sa.column("match_status", sa.String), sa.column("match_confidence", sa.Numeric),
        sa.column("match_method", sa.String), sa.column("active", sa.Boolean),
        sa.column("last_seen_at", sa.DateTime), sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = sa.func.now()
    master_ids = {}
    primary_supplier_ids = {}
    for row in bind.execute(sa.select(products)).mappings():
        supplier = bind.execute(sa.select(suppliers.c.name).where(
            suppliers.c.id == row["supplier_id"], suppliers.c.tenant_id == row["tenant_id"]
        )).scalar_one_or_none()
        if not supplier:
            continue
        normalized = " ".join(str(row["name"] or "").casefold().split())
        master_id = bind.execute(master.insert().values(
            tenant_id=row["tenant_id"], canonical_name=row["name"],
            normalized_name=normalized, category=row["category"], barcode=row["barcode"],
            base_unit=row["unit"], active=bool(row["active"]),
            created_at=now, updated_at=now,
        ).returning(master.c.id)).scalar_one()
        master_ids[row["id"]] = master_id
        primary_supplier_ids[row["id"]] = row["supplier_id"]
        price = row["current_price"]
        if price is not None and price <= 0:
            price = None
        bind.execute(supplier_product.insert().values(
            tenant_id=row["tenant_id"], supplier_id=row["supplier_id"],
            master_product_id=master_id, supplier_name=row["name"],
            description=row["description"], supplier_sku=row["supplier_sku"] or row["sku"],
            barcode=row["barcode"], price=price, currency=row["currency"] or "ILS",
            unit=row["unit"], units_per_carton=row["units_per_carton"],
            normalized_name=normalized, match_status="APPROVED",
            match_confidence=1, match_method="LEGACY_BACKFILL", active=bool(row["active"]),
            last_seen_at=now, created_at=now, updated_at=now,
        ))


    # Preserve legacy alternate supplier prices in the normalized layer.
    legacy_offers = sa.table(
        "supplier_product_offers",
        sa.column("tenant_id", sa.Integer), sa.column("product_id", sa.Integer),
        sa.column("supplier_id", sa.Integer), sa.column("supplier_sku", sa.String),
        sa.column("price", sa.Numeric), sa.column("currency", sa.String),
        sa.column("unit", sa.String), sa.column("units_per_carton", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    if sa.inspect(bind).has_table("supplier_product_offers"):
        for offer in bind.execute(sa.select(legacy_offers)).mappings():
            master_id = master_ids.get(offer["product_id"])
            if master_id is None or offer["supplier_id"] == primary_supplier_ids.get(offer["product_id"]):
                continue
            supplier_name = bind.execute(sa.select(suppliers.c.name).where(
                suppliers.c.id == offer["supplier_id"], suppliers.c.tenant_id == offer["tenant_id"]
            )).scalar_one_or_none()
            master_row = bind.execute(sa.select(
                master.c.canonical_name, master.c.normalized_name, master.c.barcode,
                master.c.base_unit, master.c.category
            ).where(master.c.id == master_id, master.c.tenant_id == offer["tenant_id"])).mappings().first()
            if not supplier_name or not master_row:
                continue
            price = offer["price"]
            if price is not None and price <= 0:
                price = None
            bind.execute(supplier_product.insert().values(
                tenant_id=offer["tenant_id"], supplier_id=offer["supplier_id"],
                master_product_id=master_id, supplier_name=master_row["canonical_name"],
                description=master_row["canonical_name"], supplier_sku=offer["supplier_sku"],
                barcode=master_row["barcode"], price=price, currency=offer["currency"] or "ILS",
                unit=offer["unit"] or master_row["base_unit"], units_per_carton=offer["units_per_carton"],
                normalized_name=master_row["normalized_name"], match_status="APPROVED",
                match_confidence=1, match_method="LEGACY_OFFER_BACKFILL", active=bool(offer["active"]),
                last_seen_at=now, created_at=now, updated_at=now,
            ))

def downgrade():
    op.drop_index("ix_supplier_products_tenant_supplier_sku", table_name="supplier_products")
    op.drop_index("ix_supplier_products_tenant_master", table_name="supplier_products")
    op.drop_index("ix_supplier_products_tenant_supplier", table_name="supplier_products")
    op.drop_index("ix_supplier_products_master_product_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_tenant_id", table_name="supplier_products")
    op.drop_table("supplier_products")
    op.drop_index("ix_master_products_tenant_normalized_name", table_name="master_products")
    op.drop_index("ix_master_products_tenant_id", table_name="master_products")
    op.drop_table("master_products")
