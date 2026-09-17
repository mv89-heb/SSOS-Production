from pathlib import Path


MIGRATION = Path("migrations/versions/20260917_db_integrity.py")


def test_stage9_migration_targets_procurement_foundation():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "20260917_procurement_foundation"' in text
    assert 'raise RuntimeError' in text
    assert 'must be applied against PostgreSQL' in text


def test_stage9_migration_enforces_same_tenant_relationships():
    text = MIGRATION.read_text(encoding="utf-8")
    required_constraints = [
        "fk_products_tenant_supplier",
        "fk_offers_tenant_product",
        "fk_offers_tenant_supplier",
        "fk_orders_tenant_supplier",
        "fk_order_items_tenant_order",
        "fk_order_items_tenant_product",
        "fk_order_items_tenant_offer",
        "fk_receipts_tenant_order",
        "fk_receipt_items_tenant_receipt",
        "fk_receipt_items_tenant_order_item",
        "fk_inventory_movements_tenant_product",
        "fk_inventory_movements_tenant_receipt",
    ]
    for constraint in required_constraints:
        assert constraint in text


def test_stage9_migration_enforces_domain_invariants():
    text = MIGRATION.read_text(encoding="utf-8")
    required_checks = [
        "ck_orders_status_valid_stage9",
        "ck_supplier_offers_price_nonnegative",
        "ck_supplier_offers_units_per_carton_positive",
        "ck_inventory_movements_type_valid_stage9",
        "ck_inventory_movements_quantity_valid_stage9",
        "ck_inventory_movements_balance_nonnegative_stage9",
        "ck_products_current_stock_nonnegative",
        "ck_products_current_price_nonnegative",
        "ck_order_items_quantity_positive_stage9",
        "ck_order_items_unit_price_nonnegative_stage9",
        "ck_receipts_status_valid_stage9",
        "ck_receipt_items_quantity_positive_stage9",
    ]
    for constraint in required_checks:
        assert constraint in text


def test_stage9_migration_fails_before_constraints_when_existing_data_is_invalid():
    text = MIGRATION.read_text(encoding="utf-8")
    assert "_assert_clean_data(bind)" in text
    assert "Repair the data before rerunning the migration" in text
    assert "offer_duplicate_product_supplier" in text
