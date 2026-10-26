from datetime import datetime, timedelta, timezone

import pytest

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_planning_service import InventoryPlanningService
from app.services.inventory_calendar_service import InventoryCalendarService


def _make_product(db, tenant_id, supplier_id, name="Test Product"):
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        name=name,
        current_price=10,
        currency="ILS",
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    return product


def test_physical_count_sets_current_stock(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id)

    movement = InventoryPlanningService(tenant_id).record_movement(
        product_id=product.id,
        movement_type=MOVEMENT_COUNT,
        quantity=42,
    )
    db.session.commit()

    assert movement.movement_type == "count"
    assert int(product.current_stock) == 42
    assert float(movement.balance_after) == 42


def test_physical_count_requires_whole_units(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id)

    with pytest.raises(ValueError, match="whole number"):
        InventoryPlanningService(tenant_id).record_movement(
            product_id=product.id,
            movement_type=MOVEMENT_COUNT,
            quantity=2.5,
        )


def test_recommendation_uses_stock_checks_and_supplier_days(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(
        tenant_id=tenant_id,
        name="Ben & Jerry",
        order_days="שני",
        delivery_days="רביעי",
    )
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id)

    now = datetime.now(timezone.utc)
    previous = InventoryMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        movement_type=MOVEMENT_COUNT,
        quantity=80,
        balance_after=80,
        occurred_at=now - timedelta(days=10),
    )
    same_day_earlier = InventoryMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        movement_type=MOVEMENT_COUNT,
        quantity=60,
        balance_after=60,
        occurred_at=now - timedelta(days=5),
    )
    current = InventoryMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        movement_type=MOVEMENT_COUNT,
        quantity=50,
        balance_after=50,
        occurred_at=now - timedelta(days=5) + timedelta(minutes=1),
    )
    product.current_stock = 50
    db.session.add_all([previous, same_day_earlier, current])
    db.session.commit()

    result = InventoryPlanningService(tenant_id).recommendation(
        product.id,
        lookback_days=60,
        safety_days=2,
    )

    assert result["stock_checks_in_period"] == 2
    assert result["estimated_depletion"] == 30
    assert result["average_daily_usage"] == pytest.approx(6, abs=0.002)
    assert result["lead_time_days"] == 2
    assert result["supplier_schedule"]["supplier_name"] == "Ben & Jerry"
    assert result["supplier_schedule"]["schedule_ready"] is True
    assert result["data_ready"] is True

    bulk_result = InventoryPlanningService(tenant_id).recommendations(
        lookback_days=60,
        safety_days=2,
    )
    product_result = next(row for row in bulk_result if row["product_id"] == product.id)
    assert product_result["stock_checks_in_period"] == 2
    assert product_result["estimated_depletion"] == 30
    assert product_result["average_daily_usage"] == pytest.approx(6, abs=0.002)


def test_recommendation_is_insufficient_without_two_checks(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id)
    product.current_stock = 20
    db.session.commit()

    result = InventoryPlanningService(tenant_id).recommendation(product.id)

    assert result["status"] == "insufficient_data"
    assert result["data_ready"] is False
    assert result["average_daily_usage"] == 0




def test_zero_stock_without_target_is_not_urgent(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id, name="Unknown stock target")
    now = datetime.now(timezone.utc)
    product.current_stock = 0
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
                          quantity=8, balance_after=8, occurred_at=now - timedelta(days=7)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
                          quantity=0, balance_after=0, occurred_at=now),
    ])
    db.session.commit()

    result = InventoryCalendarService(tenant_id).recommendation(product.id)

    assert result["status"] == "insufficient_data"
    assert result["needs_data_reason"] == "stock_target_not_configured"
    assert result["configured_stock_target"] is None


def test_zero_stock_with_counts_and_configured_target_is_urgent(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id, name="Confirmed shortage")
    product.current_stock = 0
    product.min_stock = 10
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
                          quantity=8, balance_after=8, occurred_at=now - timedelta(days=7)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
                          quantity=0, balance_after=0, occurred_at=now),
    ])
    db.session.commit()

    result = InventoryCalendarService(tenant_id).recommendation(product.id)

    assert result["status"] == "urgent"
    assert result["needs_data_reason"] is None
    assert result["configured_stock_target"] == 10

def test_carton_metrics_round_up_piece_orders():
    from decimal import Decimal

    product = Product(unit="יחידה", units_per_carton=12)
    metrics = InventoryPlanningService._carton_metrics(
        product,
        Decimal("27"),
        Decimal("60"),
        Decimal("6"),
        Decimal("48"),
        Decimal("27"),
    )

    assert metrics["stock_unit"] == "יחידה"
    assert metrics["units_per_carton"] == 12
    assert metrics["current_stock_cartons"] == pytest.approx(2.25)
    assert metrics["estimated_depletion_cartons"] == pytest.approx(5)
    assert metrics["average_daily_usage_cartons"] == pytest.approx(0.5)
    assert metrics["reorder_point_cartons"] == pytest.approx(4)
    assert metrics["recommended_order_cartons"] == 3
    assert metrics["carton_recommendation_ready"] is True


def test_carton_metrics_round_up_carton_stock_orders():
    from decimal import Decimal

    product = Product(unit="ארגז", units_per_carton=24)
    metrics = InventoryPlanningService._carton_metrics(
        product,
        Decimal("4"),
        Decimal("12"),
        Decimal("1.2"),
        Decimal("6.1"),
        Decimal("2.1"),
    )

    assert metrics["current_stock_cartons"] == 4
    assert metrics["average_daily_usage_cartons"] == pytest.approx(1.2)
    assert metrics["recommended_order_cartons"] == 3
    assert metrics["carton_recommendation_ready"] is True


def test_carton_metrics_do_not_guess_missing_pack_size():
    from decimal import Decimal

    product = Product(unit="יחידה", units_per_carton=None)
    metrics = InventoryPlanningService._carton_metrics(
        product,
        Decimal("27"),
        Decimal("60"),
        Decimal("6"),
        Decimal("48"),
        Decimal("27"),
    )

    assert metrics["current_stock_cartons"] is None
    assert metrics["recommended_order_cartons"] is None
    assert metrics["packaging_configured"] is False
    assert metrics["carton_recommendation_ready"] is False
    assert metrics["carton_recommendation_reason"] == "units_per_carton_required_for_piece_stock"



def test_recommendation_accounts_for_receipts_between_counts(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _make_product(db, tenant_id, supplier.id, name="Receipt-aware product")
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(
            tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
            quantity=100, balance_after=100, occurred_at=now - timedelta(days=10),
        ),
        InventoryMovement(
            tenant_id=tenant_id, product_id=product.id, movement_type="receipt",
            quantity=20, balance_after=90, occurred_at=now - timedelta(days=5),
        ),
        InventoryMovement(
            tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT,
            quantity=70, balance_after=70, occurred_at=now,
        ),
    ])
    product.current_stock = 70
    db.session.commit()

    service = InventoryPlanningService(tenant_id)
    single = service.recommendation(product.id, lookback_days=60, safety_days=0)
    bulk = next(
        row for row in service.recommendations(lookback_days=60, safety_days=0)
        if row["product_id"] == product.id
    )

    assert single["estimated_depletion"] == 50
    assert bulk["estimated_depletion"] == 50

def test_recommendations_include_catalog_beyond_previous_500_product_cap(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Bulk Supplier")
    db.session.add(supplier)
    db.session.flush()
    products = [
        Product(
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            name=f"Catalog Product {index:04d}",
            current_price=1,
            currency="ILS",
            active=True,
        )
        for index in range(501)
    ]
    db.session.add_all(products)
    db.session.commit()

    rows = InventoryCalendarService(tenant_id).recommendations(limit=501)

    assert len(rows) == 501
    assert len({row["product_id"] for row in rows}) == 501
