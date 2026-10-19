from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.inventory_movement import InventoryMovement, MOVEMENT_ADJUSTMENT, MOVEMENT_COUNT, MOVEMENT_RECEIPT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_calendar_service import InventoryCalendarService


def _product(db, tenant_id, supplier_id, name="Holiday Product"):
    product = Product(tenant_id=tenant_id, supplier_id=supplier_id, name=name, current_price=10, currency="ILS", active=True)
    db.session.add(product)
    db.session.flush()
    return product


def test_receipts_are_added_back_when_inferring_consumption(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=100, balance_after=100, occurred_at=now - timedelta(days=7)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_RECEIPT, quantity=20, balance_after=120, occurred_at=now - timedelta(days=4)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=80, balance_after=80, occurred_at=now),
    ])
    product.current_stock = 80
    db.session.commit()

    service = InventoryCalendarService(tenant_id)
    estimated, observed_days, receipts, checks = service._consumption_metrics(product.id, 60)

    assert checks == 2
    assert observed_days == 7
    assert estimated == 40
    assert receipts == 20


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
    db.session.add(InventoryPlanningPeriod(
        tenant_id=tenant_id,
        name="Test Holiday",
        start_date=start,
        end_date=start + timedelta(days=3),
        consumption_multiplier=2,
        active=True,
    ))
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
    second = _product(db, tenant_id, supplier.id, "Second Product")
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=first.id, movement_type=MOVEMENT_COUNT, quantity=10, balance_after=10, occurred_at=now),
        InventoryMovement(tenant_id=tenant_id, product_id=second.id, movement_type=MOVEMENT_COUNT, quantity=8, balance_after=8, occurred_at=now),
    ])
    db.session.commit()

    status = InventoryCalendarService(tenant_id).count_status()

    assert status["active_products"] == 2
    assert status["counted_products_last_7_days"] == 2
    assert status["completed"] is True
    assert status["completion_percent"] == 100

def test_adjustments_are_not_counted_as_consumption_in_calendar_planning(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Adjustment Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    now = datetime.now(timezone.utc)
    db.session.add_all([
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=100, balance_after=100, occurred_at=now - timedelta(days=10)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_ADJUSTMENT, quantity=20, balance_after=80, occurred_at=now - timedelta(days=5)),
        InventoryMovement(tenant_id=tenant_id, product_id=product.id, movement_type=MOVEMENT_COUNT, quantity=20, balance_after=20, occurred_at=now - timedelta(days=1)),
    ])
    product.current_stock = 20
    db.session.commit()

    service = InventoryCalendarService(tenant_id)
    estimated, observed_days, _, checks = service._consumption_metrics(product.id, 60)
    assert checks == 2
    assert observed_days == 9
    assert estimated == 60

    bulk = service.recommendations(lookback_days=60, safety_days=2)
    row = next(item for item in bulk if item["product_id"] == product.id)
    assert row["estimated_depletion"] == 60.0
    assert row["adjustment_delta_in_observation_period"] == -20.0



def test_schedule_for_product_preserves_explicit_base_schedule(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Schedule Override Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)

    result = InventoryCalendarService(tenant_id).schedule_for_product(
        product,
        today=date(2026, 10, 19),  # Monday
        periods=[],
        base_schedule={
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "order_days": [0],
            "delivery_days": [2],
            "next_order_date": None,
            "next_delivery_date": None,
            "order_cutoff_time": "10:00",
        },
    )

    assert result["next_order_date"] == "2026-10-19"
    assert result["next_delivery_date"] == "2026-10-21"
    assert result["order_cutoff_time"] == "10:00"


def test_explicit_inbound_quantities_reduce_recommended_order(db, tenant_a_admin, monkeypatch):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(
        tenant_id=tenant_id,
        name="Inbound Supplier",
        order_days="Monday",
        delivery_days="Wednesday",
    )
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id, "Inbound Test Product")
    product.current_stock = 5
    db.session.flush()

    service = InventoryCalendarService(tenant_id)
    monkeypatch.setattr(
        service.base,
        "recommendation",
        lambda *args, **kwargs: {"planning_horizon_days": 3},
    )
    monkeypatch.setattr(
        service,
        "_consumption_metrics",
        lambda *args, **kwargs: (Decimal("30"), Decimal("10"), Decimal("0"), 2),
    )
    monkeypatch.setattr(
        service,
        "schedule_for_product",
        lambda product, **kwargs: {
            "next_order_date": datetime.now(timezone.utc).date().isoformat(),
            "next_delivery_date": datetime.now(timezone.utc).date().isoformat(),
            "order_days": [],
            "delivery_days": [],
        },
    )
    monkeypatch.setattr(service, "periods", lambda **kwargs: [])

    without_inbound = service.recommendation(product.id, safety_days=2)
    with_inbound = service.recommendation(
        product.id, safety_days=2, inbound_quantities={product.id: Decimal("5")}
    )

    assert without_inbound["recommended_order"] == 10.0
    assert with_inbound["confirmed_inbound"] == 5.0
    assert with_inbound["recommended_order"] == 5.0
    assert with_inbound["status"] == "reorder"
