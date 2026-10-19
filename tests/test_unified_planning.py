from datetime import datetime, timedelta, timezone

from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.order import Order, STATUS_APPROVED, STATUS_CANCELLED, STATUS_SENT
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
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
    # The lead-time demand ends at delivery; the safety buffer is forecast separately.
    assert without_order["planning_horizon_days"] == without_order["lead_time_days"]

    without_safety_buffer = service.recommendation(product.id, lookback_days=60, safety_days=0)
    assert without_safety_buffer["safety_stock"] == 0

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


def test_open_inbound_subtracts_receipts_only_from_their_active_order_line(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier, product = _setup_product(db, tenant_id, "INBOUND-LINE")
    user_id = db.session.query(User).filter(User.email == "admin@acme.test").one().id

    def add_order(number, status, quantity):
        order = Order(
            tenant_id=tenant_id,
            user_id=user_id,
            supplier_id=supplier.id,
            order_number=number,
            supplier_name=supplier.name,
            status=status,
            items=[],
            currency="ILS",
        )
        db.session.add(order)
        db.session.flush()
        line = OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=10,
            currency="ILS",
        )
        db.session.add(line)
        db.session.flush()
        return order, line

    active_order, partially_received_line = add_order("PO-INBOUND-A", STATUS_APPROVED, 10)
    _, unreceived_line = add_order("PO-INBOUND-B", STATUS_SENT, 5)
    cancelled_order, cancelled_line = add_order("PO-INBOUND-C", STATUS_CANCELLED, 100)

    partial_receipt = Receipt(
        tenant_id=tenant_id,
        order_id=active_order.id,
        receipt_number="RC-INBOUND-A",
        status=RECEIPT_POSTED,
    )
    cancelled_receipt = Receipt(
        tenant_id=tenant_id,
        order_id=cancelled_order.id,
        receipt_number="RC-INBOUND-C",
        status=RECEIPT_POSTED,
    )
    db.session.add_all([partial_receipt, cancelled_receipt])
    db.session.flush()
    db.session.add_all([
        ReceiptItem(
            tenant_id=tenant_id,
            receipt_id=partial_receipt.id,
            order_item_id=partially_received_line.id,
            quantity=4,
        ),
        ReceiptItem(
            tenant_id=tenant_id,
            receipt_id=cancelled_receipt.id,
            order_item_id=cancelled_line.id,
            quantity=100,
        ),
    ])
    db.session.commit()

    inbound = InventoryUnifiedPlanningService(tenant_id)._open_inbound([product.id])

    # 10 ordered - 4 received on line A, plus 5 still due on line B.
    # The cancelled order's 100-unit receipt must not offset either active line.
    assert inbound[product.id] == 11
