"""Strengthen procurement and inventory database integrity.

Revision ID: 20260917_db_integrity
Revises: 20260917_procurement_foundation

The application already enforces tenant ownership in its repositories and
services. This migration adds the database-level backstop so a malformed or
future code path cannot create cross-tenant procurement relationships.

Production is PostgreSQL. SQLite is intentionally not used to apply this
migration because PostgreSQL composite foreign-key validation is part of the
production integrity contract.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_db_integrity"
down_revision = "20260917_procurement_foundation"
branch_labels = None
depends_on = None


def _is_postgresql(bind):
    return bind.dialect.name == "postgresql"


def _constraint_names(bind, table_name):
    inspector = sa.inspect(bind)
    names = set()
    for collection in (
        inspector.get_unique_constraints(table_name),
        inspector.get_check_constraints(table_name),
        inspector.get_foreign_keys(table_name),
    ):
        names.update(item.get("name") for item in collection if item.get("name"))
    return names


def _unique_exists(bind, table_name, name):
    return name in _constraint_names(bind, table_name)


def _fk_exists(bind, table_name, name):
    return name in _constraint_names(bind, table_name)


def _check_exists(bind, table_name, name):
    return name in _constraint_names(bind, table_name)


def _index_exists(bind, table_name, name):
    return any(index["name"] == name for index in sa.inspect(bind).get_indexes(table_name))


def _column_exists(bind, table_name, column_name):
    return any(column["name"] == column_name for column in sa.inspect(bind).get_columns(table_name))


def _assert_clean_data(bind):
    checks = [
        (
            "supplier_offer_tenant_mismatch",
            """
            SELECT COUNT(*) FROM supplier_product_offers o
            JOIN products p ON p.id = o.product_id
            WHERE o.tenant_id <> p.tenant_id
               OR NOT EXISTS (
                    SELECT 1 FROM suppliers s
                    WHERE s.id = o.supplier_id AND s.tenant_id = o.tenant_id
               )
            """,
        ),
        (
            "product_supplier_tenant_mismatch",
            """
            SELECT COUNT(*) FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM suppliers s
                WHERE s.id = p.supplier_id AND s.tenant_id = p.tenant_id
            )
            """,
        ),
        (
            "order_supplier_tenant_mismatch",
            """
            SELECT COUNT(*) FROM orders o
            WHERE o.supplier_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1 FROM suppliers s
                    WHERE s.id = o.supplier_id AND s.tenant_id = o.tenant_id
              )
            """,
        ),
        (
            "order_item_order_tenant_mismatch",
            """
            SELECT COUNT(*) FROM order_items oi
            WHERE NOT EXISTS (
                SELECT 1 FROM orders o
                WHERE o.id = oi.order_id AND o.tenant_id = oi.tenant_id
            )
            """,
        ),
        (
            "order_item_product_tenant_mismatch",
            """
            SELECT COUNT(*) FROM order_items oi
            WHERE NOT EXISTS (
                SELECT 1 FROM products p
                WHERE p.id = oi.product_id AND p.tenant_id = oi.tenant_id
            )
            """,
        ),
        (
            "order_item_offer_tenant_mismatch",
            """
            SELECT COUNT(*) FROM order_items oi
            WHERE oi.supplier_offer_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1 FROM supplier_product_offers o
                    WHERE o.id = oi.supplier_offer_id AND o.tenant_id = oi.tenant_id
              )
            """,
        ),
        (
            "receipt_order_tenant_mismatch",
            """
            SELECT COUNT(*) FROM receipts r
            WHERE NOT EXISTS (
                SELECT 1 FROM orders o
                WHERE o.id = r.order_id AND o.tenant_id = r.tenant_id
            )
            """,
        ),
        (
            "receipt_item_receipt_tenant_mismatch",
            """
            SELECT COUNT(*) FROM receipt_items ri
            WHERE NOT EXISTS (
                SELECT 1 FROM receipts r
                WHERE r.id = ri.receipt_id AND r.tenant_id = ri.tenant_id
            )
            """,
        ),
        (
            "receipt_item_order_item_tenant_mismatch",
            """
            SELECT COUNT(*) FROM receipt_items ri
            WHERE NOT EXISTS (
                SELECT 1 FROM order_items oi
                WHERE oi.id = ri.order_item_id AND oi.tenant_id = ri.tenant_id
            )
            """,
        ),
        (
            "movement_product_tenant_mismatch",
            """
            SELECT COUNT(*) FROM inventory_movements m
            WHERE NOT EXISTS (
                SELECT 1 FROM products p
                WHERE p.id = m.product_id AND p.tenant_id = m.tenant_id
            )
            """,
        ),
        (
            "movement_receipt_tenant_mismatch",
            """
            SELECT COUNT(*) FROM inventory_movements m
            WHERE m.receipt_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1 FROM receipts r
                    WHERE r.id = m.receipt_id AND r.tenant_id = m.tenant_id
              )
            """,
        ),
        (
            "offer_duplicate_product_supplier",
            """
            SELECT COUNT(*) FROM (
                SELECT tenant_id, product_id, supplier_id
                FROM supplier_product_offers
                GROUP BY tenant_id, product_id, supplier_id
                HAVING COUNT(*) > 1
            ) duplicates
            """,
        ),
    ]
    for label, sql in checks:
        count = bind.execute(sa.text(sql)).scalar_one()
        if count:
            raise RuntimeError(
                f"Stage 9 database integrity migration blocked by {label}: {count} invalid/duplicate rows. "
                "Repair the data before rerunning the migration."
            )


def _add_unique(bind, table, name, columns):
    if not _unique_exists(bind, table, name):
        op.create_unique_constraint(name, table, columns)


def _add_fk(bind, name, table, columns, referred_table, referred_columns):
    if not _fk_exists(bind, table, name):
        op.create_foreign_key(
            name,
            table,
            referred_table,
            columns,
            referred_columns,
            postgresql_not_valid=True,
        )
        op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))


def _add_check(bind, table, name, expression):
    if not _check_exists(bind, table, name):
        op.create_check_constraint(name, table, expression)


def upgrade():
    bind = op.get_bind()
    if not _is_postgresql(bind):
        raise RuntimeError(
            "20260917_db_integrity must be applied against PostgreSQL. "
            "Use the PostgreSQL CI migration gate for schema validation."
        )

    _assert_clean_data(bind)

    # A composite FK needs a unique target key. These keys are redundant from
    # an application perspective (id is already globally unique), but they are
    # required by PostgreSQL to express tenant + id as one referential unit.
    for table, name in (
        ("tenants", "uq_tenants_id_tenant_integrity"),
        ("users", "uq_users_tenant_id_integrity"),
        ("suppliers", "uq_suppliers_tenant_id_integrity"),
        ("products", "uq_products_tenant_id_integrity"),
        ("orders", "uq_orders_tenant_id_integrity"),
        ("order_items", "uq_order_items_tenant_id_integrity"),
        ("supplier_product_offers", "uq_supplier_offers_tenant_id_integrity"),
        ("receipts", "uq_receipts_tenant_id_integrity"),
    ):
        _add_unique(bind, table, name, ["tenant_id", "id"])

    # SupplierProductOffer was historically unique by product + supplier only.
    # The tenant is part of the business key and is now enforced explicitly.
    if _unique_exists(bind, "supplier_product_offers", "uq_offer_product_supplier"):
        op.drop_constraint("uq_offer_product_supplier", "supplier_product_offers", type_="unique")
    _add_unique(
        bind,
        "supplier_product_offers",
        "uq_offer_tenant_product_supplier",
        ["tenant_id", "product_id", "supplier_id"],
    )

    # Same-tenant relational integrity for procurement and inventory.
    _add_fk(
        bind, "fk_products_tenant_supplier", "products",
        ["tenant_id", "supplier_id"], "suppliers", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_offers_tenant_product", "supplier_product_offers",
        ["tenant_id", "product_id"], "products", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_offers_tenant_supplier", "supplier_product_offers",
        ["tenant_id", "supplier_id"], "suppliers", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_orders_tenant_supplier", "orders",
        ["tenant_id", "supplier_id"], "suppliers", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_order_items_tenant_order", "order_items",
        ["tenant_id", "order_id"], "orders", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_order_items_tenant_product", "order_items",
        ["tenant_id", "product_id"], "products", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_order_items_tenant_offer", "order_items",
        ["tenant_id", "supplier_offer_id"], "supplier_product_offers", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_receipts_tenant_order", "receipts",
        ["tenant_id", "order_id"], "orders", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_receipt_items_tenant_receipt", "receipt_items",
        ["tenant_id", "receipt_id"], "receipts", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_receipt_items_tenant_order_item", "receipt_items",
        ["tenant_id", "order_item_id"], "order_items", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_inventory_movements_tenant_product", "inventory_movements",
        ["tenant_id", "product_id"], "products", ["tenant_id", "id"],
    )
    _add_fk(
        bind, "fk_inventory_movements_tenant_receipt", "inventory_movements",
        ["tenant_id", "receipt_id"], "receipts", ["tenant_id", "id"],
    )

    # Domain-state and numeric invariants.
    _add_check(
        bind, "orders", "ck_orders_status_valid_stage9",
        "status IN ('draft', 'submitted', 'approved', 'sent', 'completed', 'cancelled')",
    )
    _add_check(
        bind, "supplier_product_offers", "ck_supplier_offers_price_nonnegative",
        "price >= 0",
    )
    _add_check(
        bind, "supplier_product_offers", "ck_supplier_offers_units_per_carton_positive",
        "units_per_carton IS NULL OR units_per_carton > 0",
    )
    _add_check(
        bind, "inventory_movements", "ck_inventory_movements_type_valid_stage9",
        "movement_type IN ('receipt', 'issue', 'adjustment', 'count')",
    )
    _add_check(
        bind, "inventory_movements", "ck_inventory_movements_quantity_valid_stage9",
        "((movement_type IN ('receipt', 'issue') AND quantity > 0) OR "
        "(movement_type IN ('adjustment', 'count') AND quantity >= 0))",
    )
    _add_check(
        bind, "inventory_movements", "ck_inventory_movements_balance_nonnegative_stage9",
        "balance_after IS NULL OR balance_after >= 0",
    )
    _add_check(
        bind, "products", "ck_products_current_stock_nonnegative",
        "current_stock IS NULL OR current_stock >= 0",
    )
    _add_check(
        bind, "products", "ck_products_current_price_nonnegative",
        "current_price >= 0",
    )
    _add_check(
        bind, "order_items", "ck_order_items_quantity_positive_stage9",
        "quantity > 0",
    )
    _add_check(
        bind, "order_items", "ck_order_items_unit_price_nonnegative_stage9",
        "unit_price >= 0",
    )
    _add_check(
        bind, "receipts", "ck_receipts_status_valid_stage9",
        "status IN ('draft', 'posted', 'cancelled')",
    )
    _add_check(
        bind, "receipt_items", "ck_receipt_items_quantity_positive_stage9",
        "quantity > 0",
    )

    # InventoryMovement.receipt_id is intentionally nullable for historical
    # movements; only receiving-generated movements must carry it.
    if _column_exists(bind, "inventory_movements", "receipt_id") and not _index_exists(
        bind, "inventory_movements", "ix_inventory_movements_tenant_receipt"
    ):
        op.create_index(
            "ix_inventory_movements_tenant_receipt",
            "inventory_movements",
            ["tenant_id", "receipt_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if not _is_postgresql(bind):
        raise RuntimeError("20260917_db_integrity downgrade requires PostgreSQL")

    checks = [
        ("receipt_items", "ck_receipt_items_quantity_positive_stage9"),
        ("receipts", "ck_receipts_status_valid_stage9"),
        ("order_items", "ck_order_items_unit_price_nonnegative_stage9"),
        ("order_items", "ck_order_items_quantity_positive_stage9"),
        ("products", "ck_products_current_price_nonnegative"),
        ("products", "ck_products_current_stock_nonnegative"),
        ("inventory_movements", "ck_inventory_movements_balance_nonnegative_stage9"),
        ("inventory_movements", "ck_inventory_movements_quantity_valid_stage9"),
        ("inventory_movements", "ck_inventory_movements_type_valid_stage9"),
        ("supplier_product_offers", "ck_supplier_offers_units_per_carton_positive"),
        ("supplier_product_offers", "ck_supplier_offers_price_nonnegative"),
        ("orders", "ck_orders_status_valid_stage9"),
    ]
    for table, name in checks:
        if _check_exists(bind, table, name):
            op.drop_constraint(name, table, type_="check")

    fks = [
        ("fk_inventory_movements_tenant_receipt", "inventory_movements"),
        ("fk_inventory_movements_tenant_product", "inventory_movements"),
        ("fk_receipt_items_tenant_order_item", "receipt_items"),
        ("fk_receipt_items_tenant_receipt", "receipt_items"),
        ("fk_receipts_tenant_order", "receipts"),
        ("fk_order_items_tenant_offer", "order_items"),
        ("fk_order_items_tenant_product", "order_items"),
        ("fk_order_items_tenant_order", "order_items"),
        ("fk_orders_tenant_supplier", "orders"),
        ("fk_offers_tenant_supplier", "supplier_product_offers"),
        ("fk_offers_tenant_product", "supplier_product_offers"),
        ("fk_products_tenant_supplier", "products"),
    ]
    for name, table in fks:
        if _fk_exists(bind, table, name):
            op.drop_constraint(name, table, type_="foreignkey")

    if _unique_exists(bind, "supplier_product_offers", "uq_offer_tenant_product_supplier"):
        op.drop_constraint("uq_offer_tenant_product_supplier", "supplier_product_offers", type_="unique")
    if not _unique_exists(bind, "supplier_product_offers", "uq_offer_product_supplier"):
        op.create_unique_constraint(
            "uq_offer_product_supplier", "supplier_product_offers", ["product_id", "supplier_id"]
        )

    for table, name in (
        ("receipts", "uq_receipts_tenant_id_integrity"),
        ("supplier_product_offers", "uq_supplier_offers_tenant_id_integrity"),
        ("order_items", "uq_order_items_tenant_id_integrity"),
        ("orders", "uq_orders_tenant_id_integrity"),
        ("products", "uq_products_tenant_id_integrity"),
        ("suppliers", "uq_suppliers_tenant_id_integrity"),
        ("users", "uq_users_tenant_id_integrity"),
        ("tenants", "uq_tenants_id_tenant_integrity"),
    ):
        if _unique_exists(bind, table, name):
            op.drop_constraint(name, table, type_="unique")
