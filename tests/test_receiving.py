from decimal import Decimal

from app.models.inventory_movement import InventoryMovement, MOVEMENT_RECEIPT
from app.models.order import Order, STATUS_SENT
from app.models.product import Product
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem


def _send_order(client, db, order_id):
    order = db.session.get(Order, order_id)
    order.status = STATUS_SENT
    db.session.commit()


def test_full_receipt_updates_stock_and_movement(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    assert response.status_code == 201
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, order["id"])

    received = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 5}]},
    )
    assert received.status_code == 201, received.get_json()

    receipt = received.get_json()["receipt"]
    assert receipt["status"] == RECEIPT_POSTED
    assert receipt["items"][0]["quantity"] == 5.0

    product = db.session.get(Product, product_id)
    assert product.current_stock == 5

    movement = db.session.query(InventoryMovement).filter_by(receipt_id=receipt["id"]).one()
    assert movement.movement_type == MOVEMENT_RECEIPT
    assert movement.product_id == product_id
    assert float(movement.quantity) == 5.0
    assert float(movement.balance_after) == 5.0


def test_partial_receipts_track_remaining_quantity(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=10, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, order["id"])

    first = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 4}]},
    )
    assert first.status_code == 201, first.get_json()

    second = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 6}]},
    )
    assert second.status_code == 201, second.get_json()

    receipts = db.session.query(Receipt).filter_by(order_id=order["id"]).all()
    assert len(receipts) == 2
    received_total = sum(
        Decimal(str(item.quantity))
        for receipt in receipts
        for item in db.session.query(ReceiptItem).filter_by(receipt_id=receipt.id).all()
    )
    assert received_total == Decimal("10")

    product = db.session.get(Product, product_id)
    assert product.current_stock == 10


def test_over_receipt_is_rejected_without_partial_stock_change(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, order["id"])

    rejected = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 6}]},
    )
    assert rejected.status_code == 409, rejected.get_json()
    assert db.session.query(Receipt).filter_by(order_id=order["id"]).count() == 0
    assert db.session.query(InventoryMovement).filter_by(product_id=product_id).count() == 0


def test_receipt_is_tenant_scoped(logged_in_client_a, logged_in_client_b, make_order, db):
    response, _, _ = make_order(logged_in_client_a, quantity=2, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, order["id"])

    hidden = logged_in_client_b.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 1}]},
    )
    assert hidden.status_code == 404

    listed = logged_in_client_b.get(f"/api/orders/{order['id']}/receipts")
    assert listed.status_code == 404
