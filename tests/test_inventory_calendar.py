from datetime import date, datetime, timedelta, timezone

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT, MOVEMENT_RECEIPT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_calendar_service import InventoryCalendarService


def _product(db, tenant_id, supplier_id):
    product = Product(tenant_id=tenant_id, supplier_id=supplier_id, name="Holiday Product", current_price=10, currency="ILS", active=True)
    db.session.add(product)
    db.session.flush()
    return product


def test_holiday_multiplier_changes_forecast(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier", order_days="ראשון", delivery_days="שלישי")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=50, balance_after=50, occurred_at=now - timedelta(days=14)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=36, balance_after=36, occurred_at=now - timedelta(days=7)),
    ])
    product.current_stock = 36
    start = date.today() + timedelta(days=1)
    period = InventoryPlanningPeriod(
        tenant_id=tenant_id,
        name="Test Holiday",
        start_date=start,
        end_date=start + timedelta(days=3),
        consumption_multiplier=2,
        active=True,
        created_by=tenant_a_admin[1].id,
    )
    db.session.add(period)
    db.session.commit()

    result = InventoryCalendarService(tenant_id).recommendation(product.id, lookback_days=60, safety_days=2)

    assert result["base_average_daily_usage"] > 0
    assert result["holiday_adjusted_demand"] > result["base_average_daily_usage"]
    assert result["active_planning_periods"]


def test_count_status_tracks_distinct_products(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    first = _product(db, tenant_id, supplier.id)
    second = Product(tenant_id=tenant_id, supplier_id=supplier.id, name="Second Product", current_price=10, currency="ILS", active=True)
    db.session.add(second)
    db.session.flush()
    now = datetime.now(timezone.utc)
    db.session.add(InventoryMovement(tenant_id=tenant_id, product_id=first.id, movement_type=MOVEMENT_COUNT, quantity=10, balance_after=10, occurred_at=now))
    db.session.add(InventoryMovement(tenant_id=tenant_id, product_id=second.id, movement_type=MOVEMENT_COUNT, quantity=8, balance_after=8, occurred_at=now))
    db.session.commit()

    status = InventoryCalendarService(tenant_id).count_status()

    assert status["active_products"] == 2
    assert status["counted_products_last_7_days"] == 2
    assert status["completed"] is True
    assert status["completion_percent"] == 100
