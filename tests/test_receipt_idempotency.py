from app.models.inventory_movement import InventoryMovement
from app.models.receipt import Receipt


def _send_order(db, order_id):
    from app.models.order import Order, STATUS_SENT
    order = db.session.get(Order, order_id)
    order.status = STATUS_SENT
    db.session.commit()


def test_receipt_idempotency_replays_without_duplicate_stock(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(db, order["id"])

    payload = {"items": [{"order_item_id": order_item_id, "quantity": 5}]}
    first = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json=payload,
        headers={"Idempotency-Key": "receive-order-1"},
    )
    second = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json=payload,
        headers={"Idempotency-Key": "receive-order-1"},
    )

    assert first.status_code == 201, first.get_json()
    assert second.status_code == 200, second.get_json()
    assert second.get_json()["replayed"] is True
    assert second.get_json()["receipt"]["id"] == first.get_json()["receipt"]["id"]
    assert db.session.query(Receipt).filter_by(order_id=order["id"]).count() == 1
    assert db.session.query(InventoryMovement).filter_by(product_id=product_id).count() == 1
    assert db.session.get(__import__("app.models.product", fromlist=["Product"]).Product, product_id).current_stock == 5


def test_receipt_idempotency_rejects_same_key_with_different_payload(logged_in_client_a, make_order, db):
    response, _, _ = make_order(logged_in_client_a, quantity=5, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(db, order["id"])

    first = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 2}]},
        headers={"Idempotency-Key": "receive-order-2"},
    )
    conflict = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 3}]},
        headers={"Idempotency-Key": "receive-order-2"},
    )

    assert first.status_code == 201, first.get_json()
    assert conflict.status_code == 409, conflict.get_json()
    assert db.session.query(Receipt).filter_by(order_id=order["id"]).count() == 1
