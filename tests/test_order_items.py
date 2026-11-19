from app.models.order_item import OrderItem


def test_create_order_persists_relational_order_item(logged_in_client_a, make_order, db):
    response, supplier_id, product_id = make_order(logged_in_client_a, quantity=3, price=12.5)
    assert response.status_code == 201, response.get_json()

    order = response.get_json()["order"]
    assert order["supplier_id"] == supplier_id
    assert len(order["order_items"]) == 1
    assert order["order_items"][0]["product_id"] == product_id
    assert order["order_items"][0]["quantity"] == 3.0
    assert order["order_items"][0]["unit_price"] == 12.5

    persisted = db.session.get(OrderItem, order["order_items"][0]["id"])
    assert persisted is not None
    assert persisted.tenant_id == order["tenant_id"]
    assert persisted.order_id == order["id"]


def test_update_draft_replaces_relational_order_items(logged_in_client_a, make_order, db):
    response, _, product_id = make_order(logged_in_client_a, quantity=2, price=10.0)
    assert response.status_code == 201
    order_id = response.get_json()["order"]["id"]

    updated = logged_in_client_a.put(
        f"/api/orders/{order_id}",
        json={"items": [{"product_id": product_id, "quantity": 7}]},
    )
    assert updated.status_code == 200, updated.get_json()

    order = updated.get_json()["order"]
    assert len(order["order_items"]) == 1
    assert order["order_items"][0]["quantity"] == 7.0

    rows = db.session.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    assert len(rows) == 1
    assert float(rows[0].quantity) == 7.0


def test_order_rejects_product_from_different_supplier(logged_in_client_a, make_order):
    first = make_order(logged_in_client_a, supplier_name="Supplier A", sku="SKU-A")
    assert first[0].status_code == 201
    second = make_order(logged_in_client_a, supplier_name="Supplier B", sku="SKU-B")
    assert second[0].status_code == 201

    supplier_a = first[1]
    product_b = second[2]
    response = logged_in_client_a.post(
        "/api/orders",
        json={"supplier_id": supplier_a, "items": [{"product_id": product_b, "quantity": 1}]},
    )
    assert response.status_code == 409

def test_create_order_persists_planned_order_date(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, planned_order_date="2026-11-05")
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["order"]["planned_order_date"] == "2026-11-05"


def test_update_draft_persists_planned_order_date(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    updated = logged_in_client_a.put(
        f"/api/orders/{order_id}",
        json={"planned_order_date": "2026-11-12"},
    )
    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["order"]["planned_order_date"] == "2026-11-12"


def test_create_order_rejects_invalid_planned_order_date(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, planned_order_date="not-a-date")
    assert response.status_code == 400, response.get_json()

def test_create_order_rejects_noncanonical_planned_order_date(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, planned_order_date="20261105")
    assert response.status_code == 400, response.get_json()


def test_update_draft_order_lines_is_blocked_when_invoice_is_linked(
    logged_in_client_a, make_order, db
):
    from app.models.order import Order
    from app.models.supplier_invoice import SupplierInvoice

    response, supplier_id, product_id = make_order(
        logged_in_client_a, quantity=2, price=10.0
    )
    order_id = response.get_json()["order"]["id"]
    tenant_id = response.get_json()["order"]["tenant_id"]
    invoice = SupplierInvoice(
        tenant_id=tenant_id,
        order_id=order_id,
        supplier_id=supplier_id,
        invoice_number="INV-LINKED-DRAFT-001",
        amount=20,
        currency="ILS",
    )
    db.session.add(invoice)
    db.session.commit()

    updated = logged_in_client_a.put(
        f"/api/orders/{order_id}",
        json={"items": [{"product_id": product_id, "quantity": 7}]},
    )

    assert updated.status_code == 409
    assert "Order lines cannot be changed" in updated.get_json()["message"]
    order = db.session.get(Order, order_id)
    assert order is not None
    assert len(order.order_items) == 1
    assert float(order.order_items[0].quantity) == 2.0
    assert db.session.get(SupplierInvoice, invoice.id) is not None
