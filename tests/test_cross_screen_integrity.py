def test_catalog_price_flows_to_price_intelligence_and_new_orders_without_rewriting_existing_order(logged_in_client_a):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Primary Supplier"}).get_json()["supplier"]
    product = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Integration Product", "sku": "INT-001", "current_price": 10.0, "unit": "יחידה"},
    ).get_json()["product"]

    first_order = logged_in_client_a.post(
        "/api/orders",
        json={"supplier_id": supplier["id"], "items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert first_order.status_code == 201
    first = first_order.get_json()["order"]
    assert first["items"][0]["unit_price"] == 10.0

    updated = logged_in_client_a.put(f"/api/catalog/products/{product['id']}", json={"current_price": 12.5})
    assert updated.status_code == 200
    assert updated.get_json()["product"]["current_price"] == 12.5

    catalog = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    row = next(item for item in catalog if item["id"] == product["id"])
    assert row["current_price"] == 12.5

    comparison = logged_in_client_a.get(f"/api/price-intelligence/products/{product['id']}/comparison")
    assert comparison.status_code == 200
    assert comparison.get_json()["current"]["price"] == 12.5

    second_order = logged_in_client_a.post(
        "/api/orders",
        json={"supplier_id": supplier["id"], "items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert second_order.status_code == 201
    second = second_order.get_json()["order"]
    assert second["items"][0]["unit_price"] == 12.5

    existing = logged_in_client_a.get(f"/api/orders/{first['id']}")
    assert existing.status_code == 200
    assert existing.get_json()["order"]["items"][0]["unit_price"] == 10.0


def test_supplier_offer_flows_from_catalog_to_comparison_and_does_not_change_primary_price(logged_in_client_a):
    primary = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Primary"}).get_json()["supplier"]
    alternate = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alternate"}).get_json()["supplier"]
    product = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": primary["id"], "name": "Offer Product", "sku": "INT-002", "current_price": 20.0, "unit": "יחידה"},
    ).get_json()["product"]

    offer = logged_in_client_a.post(
        f"/api/catalog/products/{product['id']}/offers",
        json={"supplier_id": alternate["id"], "price": 15.0, "unit": "יחידה", "currency": "ILS"},
    )
    assert offer.status_code == 201

    comparison = logged_in_client_a.get(f"/api/price-intelligence/products/{product['id']}/comparison")
    assert comparison.status_code == 200
    data = comparison.get_json()
    assert data["current"]["supplier_id"] == primary["id"]
    assert data["current"]["price"] == 20.0
    assert data["best_offer"]["supplier_id"] == alternate["id"]
    assert data["best_offer"]["price"] == 15.0
    assert data["saving_per_unit"] == 5.0

    catalog = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    row = next(item for item in catalog if item["id"] == product["id"])
    assert row["current_price"] == 20.0
