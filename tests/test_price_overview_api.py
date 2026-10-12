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


def test_supplier_overview_compares_approved_master_product_listings(logged_in_client_a):
    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק אב ראשי"}).get_json()["supplier"]
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק ב חלופי"}).get_json()["supplier"]

    first = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_a["id"], "supplier_name": "נייר צילום A4",
        "supplier_sku": "PAPER-A", "price": 100, "currency": "ILS", "unit": "יחידה",
    })
    assert first.status_code == 201, first.get_json()
    listing_a = first.get_json()["supplier_product"]
    approved_a = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{listing_a['id']}/approve",
        json={"create_master_product": {"canonical_name": "נייר צילום A4", "base_unit": "יחידה"}},
    )
    assert approved_a.status_code == 200, approved_a.get_json()
    master_id = approved_a.get_json()["master_product"]["id"]

    second = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_b["id"], "supplier_name": "נייר צילום A4",
        "supplier_sku": "PAPER-B", "price": 85, "currency": "ILS", "unit": "יחידה",
    })
    assert second.status_code == 201, second.get_json()
    listing_b = second.get_json()["supplier_product"]
    approved_b = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{listing_b['id']}/approve",
        json={"master_product_id": master_id},
    )
    assert approved_b.status_code == 200, approved_b.get_json()

    response = logged_in_client_a.get("/api/price-intelligence/overview?limit=300&opportunities=true")
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    row = next(item for item in payload["products"] if item.get("master_product_id") == master_id)

    assert row["supplier_count"] == 2
    assert row["current_supplier"] == supplier_a["name"]
    assert row["best_supplier"] == supplier_b["name"]
    assert row["current_price"] == 100
    assert row["best_price"] == 85
    assert row["savings_per_unit"] == 15
    assert payload["summary"]["opportunity_products"] >= 1
    assert payload["comparison_source"] == "approved_master_catalog"
