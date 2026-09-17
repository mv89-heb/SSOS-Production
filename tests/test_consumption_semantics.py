from datetime import datetime, timedelta, timezone

from app.models.inventory_movement import InventoryMovement, MOVEMENT_ADJUSTMENT, MOVEMENT_COUNT
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_consumption_planning_service import InventoryConsumptionPlanningService


def _setup(db, tenant_id):
    supplier = Supplier(
        tenant_id=tenant_id,
        name="Consumption Supplier",
        order_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
        delivery_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
        active=True,
    )
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="Consumption Product",
        sku="CONSUMPTION-1",
        current_stock=20,
        current_price=10,
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    return product


def _movement(db, tenant_id, product_id, movement_type, balance, when, quantity=None):
    db.session.add(
        InventoryMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            movement_type=movement_type,
            quantity=balance if quantity is None else quantity,
            balance_after=balance,
            occurred_at=when,
        )
    )


def test_adjustment_is_not_learned_as_consumption(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    product = _setup(db, tenant_id)
    now = datetime.now(timezone.utc)

    _movement(db, tenant_id, product.id, MOVEMENT_COUNT, 100, now - timedelta(days=10))
    # Explicit loss/correction of 20 units: stock is intentionally corrected to 80.
    _movement(db, tenant_id, product.id, MOVEMENT_ADJUSTMENT, 80, now - timedelta(days=5), quantity=20)
    _movement(db, tenant_id, product.id, MOVEMENT_COUNT, 20, now - timedelta(days=1))
    db.session.commit()

    result = InventoryConsumptionPlanningService(tenant_id).recommendation(
        product.id,
        lookback_days=60,
        safety_days=2,
    )

    # 100 -> 80 was an explicit adjustment, so only 60 units are attributed to usage:
    # 100 + (-20 adjustment) - 20 ending balance = 60 consumption.
    assert result["estimated_depletion"] == 60.0
    assert result["adjustment_delta_in_observation_period"] == -20.0
    assert round(result["average_daily_usage"], 3) == round(60 / 9, 3)


def test_positive_adjustment_offsets_consumption(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    product = _setup(db, tenant_id)
    now = datetime.now(timezone.utc)

    _movement(db, tenant_id, product.id, MOVEMENT_COUNT, 100, now - timedelta(days=10))
    # A +20 correction raises the balance to 120; ending at 60 means 60 real usage.
    _movement(db, tenant_id, product.id, MOVEMENT_ADJUSTMENT, 120, now - timedelta(days=5), quantity=20)
    _movement(db, tenant_id, product.id, MOVEMENT_COUNT, 60, now - timedelta(days=1))
    db.session.commit()

    result = InventoryConsumptionPlanningService(tenant_id).recommendation(product.id)

    assert result["estimated_depletion"] == 60.0
    assert result["adjustment_delta_in_observation_period"] == 20.0


def test_adjustment_semantics_remain_tenant_scoped(db, tenant_a_admin, tenant_b_admin):
    tenant_a = tenant_a_admin[0]["tenant"]["id"]
    tenant_b = tenant_b_admin[0]["tenant"]["id"]
    product_a = _setup(db, tenant_a)
    product_b = _setup(db, tenant_b)
    now = datetime.now(timezone.utc)

    for tenant_id, product_id in ((tenant_a, product_a.id), (tenant_b, product_b.id)):
        _movement(db, tenant_id, product_id, MOVEMENT_COUNT, 100, now - timedelta(days=10))
        _movement(db, tenant_id, product_id, MOVEMENT_COUNT, 20, now - timedelta(days=1))
    db.session.commit()

    rows = InventoryConsumptionPlanningService(tenant_a).recommendations()
    ids = {row["product_id"] for row in rows}
    assert product_a.id in ids
    assert product_b.id not in ids
