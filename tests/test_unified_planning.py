from datetime import datetime, timedelta, timezone

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.order import Order, STATUS_APPROVED
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService


def _setup_product(db, tenant_id, sku="PLAN-1"):
    supplier = Supplier(
        tenant_id=tenant_id,
        name="Planning Supplier",
        order_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
        delivery_days="ראשון,שני,שלישי,רביעי,חמישי,שישי,שבת",
        active=True,
    )
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="Planning Product",
        sku=sku,
        current_price=10,
        current_stock=20,
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    return supplier, product


def _add_count(db, tenant_id, product_id, balance, when):
    db.session.add(
        InventoryMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            movement_type=MOVEMENT_COUNT,
            quantity=balance,
            balance_after=balance,
            occurred_at=when,
        )
    )


def test_unified_planning_uses_physical_counts_and_open_inbound(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier, product = _setup_product(db, tenant_id)
    now = datetime.now(timezone.utc)
    _add_count(db, tenant_id, product.id, 100, now - timedelta(days=10))
    _add_count(db, tenant_id, product.id, 20, now - timedelta(days=1))
    db.session.commit()

    service = InventoryUnifiedPlanningService(tenant_id)
    without_order = service.recommendation(product.id, lookback_days=60, safety_days=2)
    assert without_order["average_daily_usage"] > 0
    assert without_order["open_inbound"] == 0
    assert without_order["available_for_planning"] == 20
    assert without_order["planning_engine"] == "unified-v1"

    user_id = db.session.query(User).filter(User.email == "admin@acme.test").one().id
    order = Order(
        tenant_id=tenant_id,
        user_id=user_id,
        supplier_id=supplier.id,
        order_number="PO-UNIFIED-1",
        supplier_name=supplier.name,
        status=STATUS_APPROVED,
        items=[],
        currency="ILS",
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(
        OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=20,
            unit_price=10,
            currency="ILS",
        )
    )
    db.session.commit()

    with_order = service.recommendation(product.id, lookback_days=60, safety_days=2)
    assert with_order["open_inbound"] == 20
    assert with_order["available_for_planning"] == 40
    assert with_order["recommended_order"] <= without_order["recommended_order"]


def test_unified_planning_is_tenant_scoped(db, tenant_a_admin, tenant_b_admin):
    tenant_a = tenant_a_admin[0]["tenant"]["id"]
    tenant_b = tenant_b_admin[0]["tenant"]["id"]
    _, product_a = _setup_product(db, tenant_a, "A-PLAN")
    _, product_b = _setup_product(db, tenant_b, "B-PLAN")
    now = datetime.now(timezone.utc)
    for tenant_id, product_id in ((tenant_a, product_a.id), (tenant_b, product_b.id)):
        _add_count(db, tenant_id, product_id, 100, now - timedelta(days=10))
        _add_count(db, tenant_id, product_id, 20, now - timedelta(days=1))
    db.session.commit()

    rows = InventoryUnifiedPlanningService(tenant_a).recommendations()
    ids = {row["product_id"] for row in rows}
    assert product_a.id in ids
    assert product_b.id not in ids
