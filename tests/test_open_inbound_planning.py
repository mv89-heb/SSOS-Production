from app.extensions import db
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.models.supplier import Supplier
from app.services.inventory_calendar_service import InventoryCalendarService


def _product(db, tenant_id, supplier_id, name="Inbound Product"):
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        name=name,
        current_price=10,
        currency="ILS",
        current_stock=20,
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    return product


def _order(db, tenant_id, user_id, supplier, number, status=STATUS_SENT):
    order = Order(
        tenant_id=tenant_id,
        user_id=user_id,
        supplier_id=supplier.id,
        order_number=number,
        supplier_name=supplier.name,
        status=status,
        items=[],
    )
    db.session.add(order)
    db.session.flush()
    return order


def test_open_inbound_uses_order_items(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user_id = tenant_a_admin[0]["user"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Inbound Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    order = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-1")
    db.session.add(OrderItem(tenant_id=tenant_id, order_id=order.id, product_id=product.id, quantity=100, unit_price=10, currency="ILS"))
    db.session.commit()

    result = InventoryCalendarService(tenant_id)._inbound_quantities([product.id])

    assert result[product.id] == 100


def test_partial_receipt_reduces_open_inbound(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user_id = tenant_a_admin[0]["user"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Inbound Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    order = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-2")
    item = OrderItem(tenant_id=tenant_id, order_id=order.id, product_id=product.id, quantity=100, unit_price=10, currency="ILS")
    db.session.add(item)
    db.session.flush()
    receipt = Receipt(
        tenant_id=tenant_id,
        order_id=order.id,
        receipt_number="GR-INBOUND-2",
        status=RECEIPT_POSTED,
        received_by=user_id,
    )
    db.session.add(receipt)
    db.session.flush()
    db.session.add(ReceiptItem(tenant_id=tenant_id, receipt_id=receipt.id, order_item_id=item.id, quantity=40))
    db.session.commit()

    result = InventoryCalendarService(tenant_id)._inbound_quantities([product.id])

    assert result[product.id] == 60


def test_full_receipt_removes_product_from_open_inbound(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user_id = tenant_a_admin[0]["user"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Inbound Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    order = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-3")
    item = OrderItem(tenant_id=tenant_id, order_id=order.id, product_id=product.id, quantity=100, unit_price=10, currency="ILS")
    db.session.add(item)
    db.session.flush()
    receipt = Receipt(tenant_id=tenant_id, order_id=order.id, receipt_number="GR-INBOUND-3", status=RECEIPT_POSTED, received_by=user_id)
    db.session.add(receipt)
    db.session.flush()
    db.session.add(ReceiptItem(tenant_id=tenant_id, receipt_id=receipt.id, order_item_id=item.id, quantity=100))
    db.session.commit()

    result = InventoryCalendarService(tenant_id)._inbound_quantities([product.id])

    assert product.id not in result


def test_open_inbound_aggregates_multiple_orders(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user_id = tenant_a_admin[0]["user"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Inbound Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    first = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-4A", STATUS_APPROVED)
    second = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-4B", STATUS_SENT)
    db.session.add_all([
        OrderItem(tenant_id=tenant_id, order_id=first.id, product_id=product.id, quantity=30, unit_price=10, currency="ILS"),
        OrderItem(tenant_id=tenant_id, order_id=second.id, product_id=product.id, quantity=50, unit_price=10, currency="ILS"),
    ])
    db.session.commit()

    result = InventoryCalendarService(tenant_id)._inbound_quantities([product.id])

    assert result[product.id] == 80


def test_open_inbound_is_tenant_scoped(db, tenant_a_admin, tenant_b_admin):
    tenant_a = tenant_a_admin[0]["tenant"]["id"]
    user_a = tenant_a_admin[0]["user"]["id"]
    tenant_b = tenant_b_admin[0]["tenant"]["id"]
    user_b = tenant_b_admin[0]["user"]["id"]
    supplier_a = Supplier(tenant_id=tenant_a, name="Supplier A")
    supplier_b = Supplier(tenant_id=tenant_b, name="Supplier B")
    db.session.add_all([supplier_a, supplier_b])
    db.session.flush()
    product_a = _product(db, tenant_a, supplier_a.id, "Product A")
    product_b = _product(db, tenant_b, supplier_b.id, "Product B")
    order_a = _order(db, tenant_a, user_a, supplier_a, "PO-INBOUND-5A")
    order_b = _order(db, tenant_b, user_b, supplier_b, "PO-INBOUND-5B")
    db.session.add_all([
        OrderItem(tenant_id=tenant_a, order_id=order_a.id, product_id=product_a.id, quantity=25, unit_price=10, currency="ILS"),
        OrderItem(tenant_id=tenant_b, order_id=order_b.id, product_id=product_b.id, quantity=90, unit_price=10, currency="ILS"),
    ])
    db.session.commit()

    result = InventoryCalendarService(tenant_a)._inbound_quantities()

    assert result == {product_a.id: 25}


def test_legacy_json_is_not_used_for_planning(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user_id = tenant_a_admin[0]["user"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Legacy Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = _product(db, tenant_id, supplier.id)
    order = _order(db, tenant_id, user_id, supplier, "PO-INBOUND-6")
    order.items = [{"product_id": product.id, "quantity": 999}]
    db.session.commit()

    result = InventoryCalendarService(tenant_id)._inbound_quantities([product.id])

    assert result == {}
