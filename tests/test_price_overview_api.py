def test_supplier_overview_returns_prices_and_savings(logged_in_client_a):
    supplier_a_response = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק בסיס"})
    supplier_b_response = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק חלופי"})
    assert supplier_a_response.status_code == 201, supplier_a_response.get_json()
    assert supplier_b_response.status_code == 201, supplier_b_response.get_json()
    supplier_a = supplier_a_response.get_json()["supplier"]
    supplier_b = supplier_b_response.get_json()["supplier"]

    product_response = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_a["id"],
        "name": "מוצר בדיקת השוואה",
        "sku": "OVERVIEW-TEST-001",
        "current_price": 20,
        "currency": "ILS",
        "unit": "יחידה",
    })
    assert product_response.status_code == 201, product_response.get_json()
    product = product_response.get_json()["product"]

    offer_response = logged_in_client_a.post(
        f"/api/catalog/products/{product['id']}/offers",
        json={
            "supplier_id": supplier_b["id"],
            "price": 15,
            "currency": "ILS",
            "unit": "יחידה",
        },
    )
    assert offer_response.status_code == 201, offer_response.get_json()

    response = logged_in_client_a.get("/api/price-intelligence/overview?limit=300")
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    row = next(item for item in payload["products"] if item["product_id"] == product["id"])

    assert payload["returned"] >= 1
    assert row["current_supplier"] == supplier_a["name"]
    assert row["best_supplier"] == supplier_b["name"]
    assert row["current_price"] == 20
    assert row["best_price"] == 15
    assert row["savings_per_unit"] == 5
    assert row["supplier_count"] == 2
    assert payload["summary"]["opportunity_products"] >= 1
    assert any(item["supplier_id"] == supplier_b["id"] for item in row["offers"])
