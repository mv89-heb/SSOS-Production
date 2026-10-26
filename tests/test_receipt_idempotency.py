from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
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
    assert db.session.get(Product, product_id).current_stock == 5


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


def test_partial_receipts_accumulate_stock_without_exceeding_order_quantity(
    logged_in_client_a, make_order, db
):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(db, order["id"])

    first = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 2}]},
        headers={"Idempotency-Key": "partial-receipt-1"},
    )
    second = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 3}]},
        headers={"Idempotency-Key": "partial-receipt-2"},
    )

    assert first.status_code == 201, first.get_json()
    assert second.status_code == 201, second.get_json()
    assert db.session.query(Receipt).filter_by(order_id=order["id"]).count() == 2
    assert db.session.query(InventoryMovement).filter_by(product_id=product_id).count() == 2
    assert db.session.get(Product, product_id).current_stock == 5


def test_failed_over_receipt_rolls_back_idempotency_key_and_stock(
    logged_in_client_a, make_order, db
):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(db, order["id"])

    too_much = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 6}]},
        headers={"Idempotency-Key": "retry-after-rejected-receipt"},
    )
    retry = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 5}]},
        headers={"Idempotency-Key": "retry-after-rejected-receipt"},
    )

    assert too_much.status_code == 409, too_much.get_json()
    assert retry.status_code == 201, retry.get_json()
    assert retry.get_json()["replayed"] is False
    assert db.session.query(Receipt).filter_by(order_id=order["id"]).count() == 1
    assert db.session.query(InventoryMovement).filter_by(product_id=product_id).count() == 1
    assert db.session.get(Product, product_id).current_stock == 5



def test_duplicate_receipt_number_returns_conflict_without_changing_stock(
    logged_in_client_a, make_order, db
):
    first_response, _, first_product_id = make_order(
        logged_in_client_a, quantity=1, price=10.0, sku="SKU-RECEIPT-A"
    )
    first_order = first_response.get_json()["order"]
    first_item_id = first_order["order_items"][0]["id"]
    _send_order(db, first_order["id"])

    first_receipt = logged_in_client_a.post(
        f"/api/orders/{first_order['id']}/receipts",
        json={
            "receipt_number": "RCPT-DUPLICATE-001",
            "items": [{"order_item_id": first_item_id, "quantity": 1}],
        },
        headers={"Idempotency-Key": "duplicate-receipt-number-first"},
    )
    assert first_receipt.status_code == 201, first_receipt.get_json()
    assert db.session.get(Product, first_product_id).current_stock == 1

    second_response, _, second_product_id = make_order(
        logged_in_client_a, quantity=1, price=12.0, sku="SKU-RECEIPT-B"
    )
    second_order = second_response.get_json()["order"]
    second_item_id = second_order["order_items"][0]["id"]
    _send_order(db, second_order["id"])

    duplicate = logged_in_client_a.post(
        f"/api/orders/{second_order['id']}/receipts",
        json={
            "receipt_number": "RCPT-DUPLICATE-001",
            "items": [{"order_item_id": second_item_id, "quantity": 1}],
        },
        headers={"Idempotency-Key": "duplicate-receipt-number-second"},
    )

    assert duplicate.status_code == 409, duplicate.get_json()
    assert "receipt number already exists" in duplicate.get_json()["message"].lower()
    assert db.session.query(Receipt).filter_by(order_id=second_order["id"]).count() == 0
    assert db.session.get(Product, second_product_id).current_stock in (None, 0)
