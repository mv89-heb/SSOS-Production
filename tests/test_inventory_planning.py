from datetime import datetime, timedelta, timezone

import pytest

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_planning_service import InventoryPlanningService


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
    current = InventoryMovement(
        tenant_id=tenant_id,
        product_id=product.id,
        movement_type=MOVEMENT_COUNT,
        quantity=50,
        balance_after=50,
        occurred_at=now - timedelta(days=5),
    )
    product.current_stock = 50
    db.session.add_all([previous, current])
    db.session.commit()

    result = InventoryPlanningService(tenant_id).recommendation(
        product.id,
        lookback_days=60,
        safety_days=2,
    )

    assert result["stock_checks_in_period"] == 2
    assert result["estimated_depletion"] == 30
    assert result["average_daily_usage"] == 6
    assert result["lead_time_days"] == 2
    assert result["supplier_schedule"]["supplier_name"] == "Ben & Jerry"
    assert result["supplier_schedule"]["schedule_ready"] is True
    assert result["data_ready"] is True


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
