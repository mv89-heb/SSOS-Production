from decimal import Decimal

from app.models.inventory_movement import InventoryMovement, MOVEMENT_RECEIPT
from app.models.order import Order, STATUS_SENT
from app.models.product import Product
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem


def _set_known_zero_stock(db, product_id):
    product = db.session.get(Product, product_id)
    product.current_stock = 0
    db.session.commit()


def _send_order(client, db, order_id):
    order = db.session.get(Order, order_id)
    order.status = STATUS_SENT
    db.session.commit()


def test_full_receipt_updates_stock_and_movement(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    assert response.status_code == 201
    order = response.get_json()["order"]
    _set_known_zero_stock(db, product_id)
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
    _set_known_zero_stock(db, product_id)
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


def test_receipt_rejects_order_item_from_another_order(logged_in_client_a, make_order, db):
    first_response, _, _ = make_order(
        logged_in_client_a, quantity=3, price=10.0, supplier_name="Supplier A",
        product_name="Product A", sku="CROSS-ORDER-A",
    )
    second_response, _, _ = make_order(
        logged_in_client_a, quantity=3, price=10.0, supplier_name="Supplier B",
        product_name="Product B", sku="CROSS-ORDER-B",
    )
    first_order = first_response.get_json()["order"]
    second_order = second_response.get_json()["order"]
    second_item_id = second_order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, first_order["id"])
    _send_order(logged_in_client_a, db, second_order["id"])

    rejected = logged_in_client_a.post(
        f"/api/orders/{first_order['id']}/receipts",
        json={"items": [{"order_item_id": second_item_id, "quantity": 1}]},
    )

    assert rejected.status_code == 404, rejected.get_json()
    assert db.session.query(Receipt).filter_by(order_id=first_order["id"]).count() == 0



def test_carton_receipt_converts_to_piece_stock(logged_in_client_a, db):
    supplier_response = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Carton Receipt Supplier"})
    assert supplier_response.status_code == 201, supplier_response.get_json()
    supplier_id = supplier_response.get_json()["supplier"]["id"]
    product_response = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id,
        "name": "Carton receipt milk",
        "sku": "MILK-CARTON-RECEIPT",
        "current_price": 2,
        "unit": "יחידה",
        "units_per_carton": 12,
        "current_stock": 0,
    })
    assert product_response.status_code == 201, product_response.get_json()
    product_id = product_response.get_json()["product"]["id"]
    order_response = logged_in_client_a.post("/api/orders", json={
        "supplier_id": supplier_id,
        "items": [{"product_id": product_id, "quantity": 3, "quantity_unit": "carton"}],
    })
    assert order_response.status_code == 201, order_response.get_json()
    order = order_response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _send_order(logged_in_client_a, db, order["id"])

    received = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 2}]},
    )
    assert received.status_code == 201, received.get_json()
    product = db.session.get(Product, product_id)
    assert product.current_stock == 24

    movement = db.session.query(InventoryMovement).filter_by(product_id=product_id).one()
    assert float(movement.quantity) == 24
    assert float(movement.balance_after) == 24
    receipt_item = db.session.query(ReceiptItem).filter_by(order_item_id=order_item_id).one()
    assert float(receipt_item.quantity) == 2



def test_receipt_can_preserve_unknown_delivery_date(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=1, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _set_known_zero_stock(db, product_id)
    _send_order(logged_in_client_a, db, order["id"])

    received = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={
            "receipt_number": "RECEIPT-UNKNOWN-DATE-001",
            "received_at": None,
            "items": [{"order_item_id": order_item_id, "quantity": 1}],
        },
    )
    assert received.status_code == 201, received.get_json()
    assert received.get_json()["receipt"]["received_at"] is None
    movement = InventoryMovement.query.filter_by(
        receipt_id=received.get_json()["receipt"]["id"]
    ).one()
    assert movement.occurred_at is not None


def test_damaged_units_are_recorded_but_only_accepted_units_enter_stock_and_order_balance(
    logged_in_client_a, make_order, db
):
    response, _, product_id = make_order(logged_in_client_a, quantity=5, price=10.0)
    assert response.status_code == 201
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _set_known_zero_stock(db, product_id)
    _send_order(logged_in_client_a, db, order["id"])

    first = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{
            "order_item_id": order_item_id,
            "quantity": 3,
            "damaged_quantity": 1,
            "damage_notes": "אריזה קרועה",
        }]},
    )
    assert first.status_code == 201, first.get_json()
    first_item = first.get_json()["receipt"]["items"][0]
    assert first_item["quantity"] == 3.0
    assert first_item["damaged_quantity"] == 1.0
    assert first_item["accepted_quantity"] == 2.0
    assert first_item["damage_notes"] == "אריזה קרועה"
    assert db.session.get(Product, product_id).current_stock == 2
    first_movement = InventoryMovement.query.filter_by(receipt_id=first.get_json()["receipt"]["id"]).one()
    assert float(first_movement.quantity) == 2.0
    assert "damaged not stocked" in first_movement.note

    replacement = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 3}]},
    )
    assert replacement.status_code == 201, replacement.get_json()
    assert db.session.get(Product, product_id).current_stock == 5
    received_items = ReceiptItem.query.filter_by(order_item_id=order_item_id).all()
    assert sum(Decimal(str(item.quantity)) for item in received_items) == Decimal("6")
    assert sum(Decimal(str(item.quantity - item.damaged_quantity)) for item in received_items) == Decimal("5")


def test_damaged_receipt_requires_reason_and_cannot_exceed_physical_quantity(
    logged_in_client_a, make_order, db
):
    response, _, product_id = make_order(logged_in_client_a, quantity=2, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _set_known_zero_stock(db, product_id)
    _send_order(logged_in_client_a, db, order["id"])

    missing_reason = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 1, "damaged_quantity": 1}]},
    )
    assert missing_reason.status_code == 400

    over_damaged = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{
            "order_item_id": order_item_id,
            "quantity": 1,
            "damaged_quantity": 2,
            "damage_notes": "לא תקין",
        }]},
    )
    assert over_damaged.status_code == 400
    assert Receipt.query.filter_by(order_id=order["id"]).count() == 0
    assert db.session.get(Product, product_id).current_stock == 0
    assert InventoryMovement.query.filter_by(product_id=product_id).count() == 0


def test_fully_damaged_receipt_is_recorded_without_zero_or_positive_stock_movement(
    logged_in_client_a, make_order, db
):
    response, _, product_id = make_order(logged_in_client_a, quantity=2, price=10.0)
    order = response.get_json()["order"]
    order_item_id = order["order_items"][0]["id"]
    _set_known_zero_stock(db, product_id)
    _send_order(logged_in_client_a, db, order["id"])

    damaged = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{
            "order_item_id": order_item_id,
            "quantity": 2,
            "damaged_quantity": 2,
            "damage_notes": "כל היחידות נשברו בהובלה",
        }]},
    )
    assert damaged.status_code == 201, damaged.get_json()
    item = damaged.get_json()["receipt"]["items"][0]
    assert item["quantity"] == 2.0
    assert item["damaged_quantity"] == 2.0
    assert item["accepted_quantity"] == 0.0
    assert db.session.get(Product, product_id).current_stock == 0
    assert InventoryMovement.query.filter_by(receipt_id=damaged.get_json()["receipt"]["id"]).count() == 0

    replacement = logged_in_client_a.post(
        f"/api/orders/{order['id']}/receipts",
        json={"items": [{"order_item_id": order_item_id, "quantity": 2}]},
    )
    assert replacement.status_code == 201, replacement.get_json()
    assert db.session.get(Product, product_id).current_stock == 2
