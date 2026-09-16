def _create_product(client, name="Milk", sku="MILK-1", stock=10, minimum=3, target=12, barcode=None):
    supplier = client.post("/api/catalog/suppliers", json={"name": "Warehouse Supplier"})
    assert supplier.status_code == 201, supplier.get_json()
    supplier_id = supplier.get_json()["supplier"]["id"]
    payload = {
        "supplier_id": supplier_id,
        "name": name,
        "sku": sku,
        "current_price": 10,
        "current_stock": stock,
        "min_stock": minimum,
        "recommended_stock": target,
        "unit": "UNIT",
    }
    if barcode is not None:
        payload["barcode"] = barcode
    response = client.post("/api/catalog/products", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["product"]["id"]


def test_inventory_summary_and_movements(logged_in_client_a):
    product_id = _create_product(logged_in_client_a)
    summary = logged_in_client_a.get("/api/inventory/summary")
    assert summary.status_code == 200
    body = summary.get_json()
    assert body["success"] is True
    assert any(product["id"] == product_id for product in body["products"])

    receipt = logged_in_client_a.post("/api/inventory/movements", json={"product_id": product_id, "movement_type": "receipt", "quantity": 5, "note": "קליטה למחסן"})
    assert receipt.status_code == 201, receipt.get_json()
    assert receipt.get_json()["movement"]["balance_after"] == 15

    count = logged_in_client_a.post("/api/inventory/movements", json={"product_id": product_id, "movement_type": "count", "quantity": 14})
    assert count.status_code == 201, count.get_json()
    assert count.get_json()["movement"]["balance_after"] == 14

    history = logged_in_client_a.get(f"/api/inventory/products/{product_id}/movements")
    assert history.status_code == 200
    movements = history.get_json()["movements"]
    assert len(movements) >= 2
    assert movements[0]["product_id"] == product_id


def test_zero_stock_count_is_valid(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, stock=4)
    response = logged_in_client_a.post("/api/inventory/movements", json={"product_id": product_id, "movement_type": "count", "quantity": 0})
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["movement"]["balance_after"] == 0


def test_inventory_issue_cannot_make_stock_negative(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, stock=2)
    response = logged_in_client_a.post("/api/inventory/movements", json={"product_id": product_id, "movement_type": "issue", "quantity": 3})
    assert response.status_code == 400
    assert "negative" in response.get_json()["message"]


def test_inventory_is_tenant_scoped(logged_in_client_a, logged_in_client_b):
    product_id = _create_product(logged_in_client_a, sku="TENANT-A-1")
    response = logged_in_client_b.get(f"/api/inventory/products/{product_id}/movements")
    assert response.status_code == 404
    movement = logged_in_client_b.post("/api/inventory/movements", json={"product_id": product_id, "movement_type": "count", "quantity": 99})
    assert movement.status_code == 404


def test_inventory_lookup_by_barcode_and_sku(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, sku="MILK-SKU-42", barcode="7290001234567")
    barcode = logged_in_client_a.get("/api/inventory/products/lookup?value=7290001234567")
    assert barcode.status_code == 200, barcode.get_json()
    assert barcode.get_json()["product"]["id"] == product_id
    sku = logged_in_client_a.get("/api/inventory/products/lookup?value=MILK-SKU-42")
    assert sku.status_code == 200, sku.get_json()
    assert sku.get_json()["product"]["id"] == product_id


def test_inventory_lookup_is_tenant_scoped(logged_in_client_a, logged_in_client_b):
    _create_product(logged_in_client_a, sku="TENANT-A-LOOKUP", barcode="7290099999999")
    barcode = logged_in_client_b.get("/api/inventory/products/lookup?value=7290099999999")
    assert barcode.status_code == 404
    sku = logged_in_client_b.get("/api/inventory/products/lookup?value=TENANT-A-LOOKUP")
    assert sku.status_code == 404


def test_inventory_lookup_requires_value(logged_in_client_a):
    response = logged_in_client_a.get("/api/inventory/products/lookup")
    assert response.status_code == 400


def test_new_products_keep_barcode_optional_until_bulk_generation(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, sku="OPTIONAL-BARCODE")
    product = logged_in_client_a.get(f"/api/catalog/products/{product_id}")
    assert product.status_code == 200, product.get_json()
    assert product.get_json()["product"]["barcode"] is None


def test_generate_internal_barcodes_for_existing_missing_product(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, sku="MISSING-BARCODE")
    response = logged_in_client_a.post("/api/inventory/barcodes/generate", json={})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["generated_count"] == 1
    generated = next(product for product in body["products"] if product["id"] == product_id)
    assert generated["barcode"].isdigit()
    assert generated["barcode"].endswith(f"{product_id:08d}")

    repeat = logged_in_client_a.post("/api/inventory/barcodes/generate", json={})
    assert repeat.status_code == 200, repeat.get_json()
    assert repeat.get_json()["generated_count"] == 0
    assert repeat.get_json()["skipped_count"] >= 1

    lookup = logged_in_client_a.get(f"/api/inventory/products/lookup?value={generated['barcode']}")
    assert lookup.status_code == 200, lookup.get_json()
    assert lookup.get_json()["product"]["id"] == product_id


def test_generate_barcodes_preserves_existing_barcode(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, sku="HAS-BARCODE", barcode="7290012345678")
    response = logged_in_client_a.post("/api/inventory/barcodes/generate", json={"product_ids": [product_id]})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["generated_count"] == 0
    assert body["skipped_count"] == 1


def test_generate_barcodes_is_tenant_scoped(logged_in_client_a, logged_in_client_b):
    product_id = _create_product(logged_in_client_a, sku="TENANT-A-BARCODE")
    response = logged_in_client_b.post("/api/inventory/barcodes/generate", json={"product_ids": [product_id]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["generated_count"] == 0
    assert response.get_json()["products"] == []
