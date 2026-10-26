from datetime import datetime, timedelta, timezone

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService


def test_recommendations_deduplicate_same_day_counts_and_expose_carton_usage(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(
        tenant_id=tenant_id,
        name="Carton Metrics Supplier",
        active=True,
        order_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
        delivery_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
    )
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="Carton Metrics Product",
        unit="ארגז",
        current_stock=50,
        min_stock=10,
        recommended_stock=20,
        current_price=10,
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    now = datetime.now(timezone.utc)
    events = [
        (100, now - timedelta(days=10)),
        (60, now - timedelta(days=5)),
        (80, now - timedelta(days=5) + timedelta(minutes=1)),  # same-day correction; latest count wins
        (50, now - timedelta(days=1)),
    ]
    for balance, occurred_at in events:
        db.session.add(InventoryMovement(
            tenant_id=tenant_id,
            product_id=product.id,
            movement_type=MOVEMENT_COUNT,
            quantity=balance,
            balance_after=balance,
            occurred_at=occurred_at,
        ))
    db.session.commit()

    row = next(
        item for item in InventoryUnifiedPlanningService(tenant_id).recommendations(limit=100)
        if item["product_id"] == product.id
    )

    # 100 -> 80 -> 50 over nine observed days; the same-day 60 recount is ignored.
    assert row["stock_checks_in_period"] == 3
    assert row["estimated_depletion"] == 50.0
    assert row["observed_days"] == 9.0
    assert row["average_daily_usage_cartons"] == row["average_daily_usage"]
    # Weekly usage is rounded from the underlying rate, not from the already-rounded daily display.
    assert row["weekly_usage_cartons"] == round(row["estimated_depletion"] / row["observed_days"] * 7, 3)
    assert row["current_stock_cartons"] == 50.0
    assert row["carton_recommendation_ready"] is True
