"""Add relational procurement foundation.

Revision ID: 20260917_procurement_foundation
Revises: 20260916_inventory_periods

This migration is intentionally additive. The legacy orders.items JSON column is
kept for compatibility while OrderItem becomes the operational line-item model.
Supplier linkage is initially nullable so existing orders whose supplier cannot
be resolved unambiguously are not destroyed during deployment.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_procurement_foundation"
down_revision = "20260916_inventory_periods"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name):
    return table_name in sa.inspect(bind).get_table_names()


def _column_exists(bind, table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(bind).get_columns(table_name))


def _index_exists(bind, table_name, index_name):
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def _constraint_exists(bind, table_name, constraint_name):
    inspector = sa.inspect(bind)
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    ) or any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    ) or any(
        fk.get("name") == constraint_name
        for fk in inspector.get_foreign_keys(table_name)
    )


def upgrade():
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # Order foundation: retain supplier_name/contact/email as immutable
    # snapshots, while adding the relational supplier reference.
    # ------------------------------------------------------------------
    if not _column_exists(bind, "orders", "supplier_id"):
        op.add_column("orders", sa.Column("supplier_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_orders_supplier_id_suppliers",
            "orders",
            "suppliers",
            ["supplier_id"],
            ["id"],
        )
        op.create_index("ix_orders_supplier_id", "orders", ["supplier_id"], unique=False)

    # Resolve an existing supplier only when the tenant + supplier name maps
    # to exactly one supplier. Ambiguous/unmatched legacy orders remain
    # nullable and will be resolved by the procurement application flow.
    bind.execute(sa.text("""
        UPDATE orders AS o
        SET supplier_id = matches.supplier_id
        FROM (
            SELECT o2.id AS order_id, MIN(s.id) AS supplier_id
            FROM orders AS o2
            JOIN suppliers AS s
              ON s.tenant_id = o2.tenant_id
             AND lower(trim(s.name)) = lower(trim(o2.supplier_name))
            WHERE o2.supplier_id IS NULL
            GROUP BY o2.id
            HAVING COUNT(s.id) = 1
        ) AS matches
        WHERE o.id = matches.order_id
          AND o.supplier_id IS NULL
    """))

    if not _constraint_exists(bind, "orders", "uq_orders_tenant_order_number"):
        duplicate_orders = bind.execute(sa.text("""
            SELECT COUNT(*)
            FROM (
                SELECT tenant_id, order_number
                FROM orders
                GROUP BY tenant_id, order_number
                HAVING COUNT(*) > 1
            ) duplicates
        """)).scalar_one()
        if duplicate_orders:
            raise RuntimeError(
                "Cannot create tenant-scoped order number uniqueness: "
                f"{duplicate_orders} duplicate tenant/order_number groups exist. "
                "Resolve duplicates before rerunning this migration."
            )
        op.create_unique_constraint(
            "uq_orders_tenant_order_number",
            "orders",
            ["tenant_id", "order_number"],
        )

    if not _constraint_exists(bind, "orders", "ck_orders_status_valid"):
        op.execute(sa.text("""
            ALTER TABLE orders
            ADD CONSTRAINT ck_orders_status_valid
            CHECK (status IN ('draft', 'submitted', 'approved', 'sent', 'completed', 'cancelled'))
            NOT VALID
        """))

    # ------------------------------------------------------------------
    # Relational operational order lines.
    # ------------------------------------------------------------------
    if not _table_exists(bind, "order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("supplier_offer_id", sa.Integer(), nullable=True),
            sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
            sa.Column("product_snapshot", sa.JSON(), nullable=True),
            sa.Column("offer_snapshot", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_order_items_tenant"),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_order_items_order", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_order_items_product"),
            sa.ForeignKeyConstraint(["supplier_offer_id"], ["supplier_product_offers.id"], name="fk_order_items_supplier_offer"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
            sa.CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price_nonnegative"),
        )

    for name, columns in (
        ("ix_order_items_tenant", ["tenant_id"]),
        ("ix_order_items_order_id", ["order_id"]),
        ("ix_order_items_product_id", ["product_id"]),
        ("ix_order_items_supplier_offer_id", ["supplier_offer_id"]),
        ("ix_order_items_tenant_order", ["tenant_id", "order_id"]),
        ("ix_order_items_tenant_product", ["tenant_id", "product_id"]),
        ("ix_order_items_tenant_offer", ["tenant_id", "supplier_offer_id"]),
    ):
        if not _index_exists(bind, "order_items", name):
            op.create_index(name, "order_items", columns, unique=False)

    # Validate legacy JSON before backfill. Invalid legacy rows are safer to
    # block than to silently omit from the new operational model.
    invalid_json_rows = bind.execute(sa.text("""
        SELECT COUNT(*)
        FROM orders
        WHERE items IS NOT NULL
          AND jsonb_typeof(items::jsonb) <> 'array'
    """)).scalar_one()
    if invalid_json_rows:
        raise RuntimeError(
            f"Cannot backfill order_items: {invalid_json_rows} orders have non-array items JSON."
        )

    invalid_items = bind.execute(sa.text("""
        SELECT COUNT(*)
        FROM orders AS o
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(o.items::jsonb, '[]'::jsonb)) AS item
        WHERE NOT (
            item ? 'product_id'
            AND (item->>'product_id') ~ '^[0-9]+$'
            AND item ? 'quantity'
            AND (item->>'quantity') ~ '^[0-9]+(\\.[0-9]+)?$'
            AND (item->>'quantity')::numeric > 0
            AND item ? 'unit_price'
            AND (item->>'unit_price') ~ '^-?[0-9]+(\\.[0-9]+)?$'
            AND (item->>'unit_price')::numeric >= 0
        )
    """)).scalar_one()
    if invalid_items:
        raise RuntimeError(
            f"Cannot backfill order_items: {invalid_items} legacy order items have invalid product, quantity, or price data."
        )

    bind.execute(sa.text("""
        INSERT INTO order_items (
            tenant_id,
            order_id,
            product_id,
            supplier_offer_id,
            quantity,
            unit_price,
            currency,
            product_snapshot,
            offer_snapshot,
            created_at,
            updated_at
        )
        SELECT
            o.tenant_id,
            o.id,
            (item->>'product_id')::integer,
            NULL,
            (item->>'quantity')::numeric,
            (item->>'unit_price')::numeric,
            COALESCE(NULLIF(item->>'currency', ''), o.currency, 'ILS'),
            item,
            NULL,
            COALESCE(o.created_at, CURRENT_TIMESTAMP),
            COALESCE(o.updated_at, CURRENT_TIMESTAMP)
        FROM orders AS o
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(o.items::jsonb, '[]'::jsonb)) AS item
        WHERE NOT EXISTS (
            SELECT 1
            FROM order_items oi
            WHERE oi.order_id = o.id
        )
    """))

    # ------------------------------------------------------------------
    # Receiving foundation. One order may have many receipts, and one receipt
    # may contain multiple lines. This enables partial receiving without
    # changing Order.status semantics.
    # ------------------------------------------------------------------
    if not _table_exists(bind, "receipts"):
        op.create_table(
            "receipts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("receipt_number", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("received_by", sa.Integer(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_receipts_tenant"),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_receipts_order"),
            sa.ForeignKeyConstraint(["received_by"], ["users.id"], name="fk_receipts_received_by"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "receipt_number", name="uq_receipts_tenant_receipt_number"),
            sa.CheckConstraint("status IN ('draft', 'posted', 'cancelled')", name="ck_receipts_status_valid"),
        )

    for name, columns in (
        ("ix_receipts_tenant", ["tenant_id"]),
        ("ix_receipts_order_id", ["order_id"]),
        ("ix_receipts_received_by", ["received_by"]),
        ("ix_receipts_tenant_order", ["tenant_id", "order_id"]),
        ("ix_receipts_tenant_status", ["tenant_id", "status"]),
        ("ix_receipts_tenant_received_at", ["tenant_id", "received_at"]),
    ):
        if not _index_exists(bind, "receipts", name):
            op.create_index(name, "receipts", columns, unique=False)

    if not _table_exists(bind, "receipt_items"):
        op.create_table(
            "receipt_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("receipt_id", sa.Integer(), nullable=False),
            sa.Column("order_item_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_receipt_items_tenant"),
            sa.ForeignKeyConstraint(["receipt_id"], ["receipts.id"], name="fk_receipt_items_receipt", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], name="fk_receipt_items_order_item"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("receipt_id", "order_item_id", name="uq_receipt_items_receipt_order_item"),
            sa.CheckConstraint("quantity > 0", name="ck_receipt_items_quantity_positive"),
        )

    for name, columns in (
        ("ix_receipt_items_tenant", ["tenant_id"]),
        ("ix_receipt_items_receipt_id", ["receipt_id"]),
        ("ix_receipt_items_order_item_id", ["order_item_id"]),
        ("ix_receipt_items_tenant_receipt", ["tenant_id", "receipt_id"]),
        ("ix_receipt_items_tenant_order_item", ["tenant_id", "order_item_id"]),
    ):
        if not _index_exists(bind, "receipt_items", name):
            op.create_index(name, "receipt_items", columns, unique=False)

    # Explicit receipt linkage is safer than relying on the generic reference
    # fields for the core receiving -> stock transaction.
    if not _column_exists(bind, "inventory_movements", "receipt_id"):
        op.add_column("inventory_movements", sa.Column("receipt_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_inventory_movements_receipt_id_receipts",
            "inventory_movements",
            "receipts",
            ["receipt_id"],
            ["id"],
        )
        op.create_index(
            "ix_inventory_movements_receipt_id",
            "inventory_movements",
            ["receipt_id"],
            unique=False,
        )
        op.create_index(
            "ix_inventory_movements_tenant_receipt",
            "inventory_movements",
            ["tenant_id", "receipt_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()

    if _column_exists(bind, "inventory_movements", "receipt_id"):
        if _index_exists(bind, "inventory_movements", "ix_inventory_movements_tenant_receipt"):
            op.drop_index("ix_inventory_movements_tenant_receipt", table_name="inventory_movements")
        if _index_exists(bind, "inventory_movements", "ix_inventory_movements_receipt_id"):
            op.drop_index("ix_inventory_movements_receipt_id", table_name="inventory_movements")
        if _constraint_exists(bind, "inventory_movements", "fk_inventory_movements_receipt_id_receipts"):
            op.drop_constraint(
                "fk_inventory_movements_receipt_id_receipts",
                "inventory_movements",
                type_="foreignkey",
            )
        op.drop_column("inventory_movements", "receipt_id")

    if _table_exists(bind, "receipt_items"):
        op.drop_table("receipt_items")
    if _table_exists(bind, "receipts"):
        op.drop_table("receipts")
    if _table_exists(bind, "order_items"):
        op.drop_table("order_items")

    if _constraint_exists(bind, "orders", "ck_orders_status_valid"):
        op.drop_constraint("ck_orders_status_valid", "orders", type_="check")
    if _constraint_exists(bind, "orders", "uq_orders_tenant_order_number"):
        op.drop_constraint("uq_orders_tenant_order_number", "orders", type_="unique")
    if _column_exists(bind, "orders", "supplier_id"):
        if _index_exists(bind, "orders", "ix_orders_supplier_id"):
            op.drop_index("ix_orders_supplier_id", table_name="orders")
        if _constraint_exists(bind, "orders", "fk_orders_supplier_id_suppliers"):
            op.drop_constraint("fk_orders_supplier_id_suppliers", "orders", type_="foreignkey")
        op.drop_column("orders", "supplier_id")
