def test_supplier_inline_fields_are_editable(logged_in_client_a):
    created = logged_in_client_a.post(
        "/api/catalog/suppliers",
        json={"name": "Supplier", "customer_number": "100"},
    ).get_json()["supplier"]

    response = logged_in_client_a.put(
        f"/api/catalog/suppliers/{created['id']}",
        json={"customer_number": "200", "delivery_days": "שני, רביעי", "order_days": "ראשון, שלישי"},
    )

    assert response.status_code == 200, response.get_json()
    supplier = response.get_json()["supplier"]
    assert supplier["customer_number"] == "200"
    assert supplier["delivery_days"] == "שני, רביעי"
    assert supplier["order_days"] == "ראשון, שלישי"


def test_product_inline_fields_are_editable_without_rewriting_order_snapshot(logged_in_client_a, make_order):
    order_response, supplier_id, product_id = make_order(logged_in_client_a, price=10.0)
    assert order_response.status_code == 201

    response = logged_in_client_a.put(
        f"/api/catalog/products/{product_id}",
        json={"sku": "SKU-UPDATED", "barcode": "7291234567890", "category": "מוצרי חלב", "current_stock": 20},
    )

    assert response.status_code == 200, response.get_json()
    product = response.get_json()["product"]
    assert product["sku"] == "SKU-UPDATED"
    assert product["barcode"] == "7291234567890"
    assert product["category"] == "מוצרי חלב"
    assert product["current_stock"] == 20
