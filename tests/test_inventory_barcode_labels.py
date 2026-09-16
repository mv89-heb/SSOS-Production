def _create_product(client, sku):
    supplier = client.post("/api/catalog/suppliers", json={"name": f"Supplier {sku}"})
    assert supplier.status_code == 201, supplier.get_json()
    product = client.post("/api/catalog/products", json={
        "supplier_id": supplier.get_json()["supplier"]["id"],
        "name": f"Test Product {sku}",
        "sku": sku,
        "current_price": 10,
    })
    assert product.status_code == 201, product.get_json()
    return product.get_json()["product"]["id"]


def test_print_barcode_labels_returns_pdf(logged_in_client_a):
    product_id = _create_product(logged_in_client_a, "PDF-LABEL-1")
    response = logged_in_client_a.post("/api/inventory/barcodes/labels", json={"product_ids": [product_id]})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_print_barcode_labels_requires_product_ids(logged_in_client_a):
    response = logged_in_client_a.post("/api/inventory/barcodes/labels", json={})
    assert response.status_code == 400, response.get_json()
