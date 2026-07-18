def test_tenant_catalog_isolation(logged_in_client_a, logged_in_client_b):
    # Tenant A creates a supplier
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Tenant A Supplier"})

    # Tenant B should see an empty list
    resp = logged_in_client_b.get("/api/catalog/suppliers")
    assert resp.status_code == 200
    assert len(resp.get_json()["suppliers"]) == 0


def test_list_products_active_only_filter(logged_in_client_a):
    s_resp = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Filter Test Supplier"})
    s_id = s_resp.get_json()["supplier"]["id"]

    active = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Active Product", "sku": "ACT1", "current_price": 10.0,
    })
    inactive_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Inactive Product", "sku": "INA1", "current_price": 10.0, "active": False,
    }).get_json()["product"]["id"]

    all_products = logged_in_client_a.get(f"/api/catalog/products?supplier_id={s_id}")
    assert len(all_products.get_json()["products"]) == 2

    active_only = logged_in_client_a.get(f"/api/catalog/products?supplier_id={s_id}&active=true")
    names = [p["name"] for p in active_only.get_json()["products"]]
    assert "Active Product" in names
    assert "Inactive Product" not in names
    assert inactive_id not in [p["id"] for p in active_only.get_json()["products"]]
    assert active.status_code == 201


def test_get_single_product(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Widget", "sku": "W1", "current_price": 5.0,
    }).get_json()["product"]["id"]

    resp = logged_in_client_a.get(f"/api/catalog/products/{p_id}")
    assert resp.status_code == 200
    assert resp.get_json()["product"]["name"] == "Widget"


def test_get_nonexistent_product_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/catalog/products/999999")
    assert resp.status_code == 404


def test_get_single_supplier(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Detail Supplier"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.get(f"/api/catalog/suppliers/{s_id}")
    assert resp.status_code == 200
    assert resp.get_json()["supplier"]["name"] == "Detail Supplier"


def test_get_nonexistent_supplier_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/catalog/suppliers/999999")
    assert resp.status_code == 404


def test_update_supplier(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Old Name"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.put(f"/api/catalog/suppliers/{s_id}", json={"name": "New Name", "phone": "12345"})
    assert resp.status_code == 200
    supplier = resp.get_json()["supplier"]
    assert supplier["name"] == "New Name"
    assert supplier["phone"] == "12345"


def test_soft_delete_supplier_via_active_flag(logged_in_client_a):
    """Suppliers/products use active=False as the 'soft delete' — the row
    stays, so any order that already referenced them keeps working."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Deactivate Me"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.put(f"/api/catalog/suppliers/{s_id}", json={"active": False})
    assert resp.status_code == 200
    assert resp.get_json()["supplier"]["active"] is False

    active_only = logged_in_client_a.get("/api/catalog/suppliers?active=true")
    ids = [s["id"] for s in active_only.get_json()["suppliers"]]
    assert s_id not in ids

    all_suppliers = logged_in_client_a.get("/api/catalog/suppliers")
    ids_all = [s["id"] for s in all_suppliers.get_json()["suppliers"]]
    assert s_id in ids_all


def test_employee_cannot_update_supplier(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    s_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.put(f"/api/catalog/suppliers/{s_id}", json={"name": "Hijacked"})
    assert resp.status_code == 403


def test_me_includes_tenant_info(logged_in_client_a):
    resp = logged_in_client_a.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tenant"]["name"] == "Acme Co"
    assert body["tenant"]["id"] == body["user"]["tenant_id"]


def test_audit_log_includes_user_email(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Audit Email Test"})
    resp = logged_in_client_a.get("/api/audit")
    logs = resp.get_json()["logs"]
    matching = [log for log in logs if log["action"] == "catalog.supplier_created"]
    assert matching
    assert matching[0]["user_email"] == "admin@acme.test"


def test_order_snapshot_integrity(logged_in_client_a):
    # 1. Setup Supplier and Product
    s_resp = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Snapshot Test Supplier"})
    s_id = s_resp.get_json()["supplier"]["id"]

    p_resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Test Product", "sku": "SKU001", "current_price": 100.0
    })
    p_id = p_resp.get_json()["product"]["id"]

    # 2. Create Order (line items copied from the catalog at this moment)
    o_resp = logged_in_client_a.post("/api/orders", json={
        "supplier_id": s_id,
        "items": [{"product_id": p_id, "quantity": 5}]
    })
    order = o_resp.get_json()["order"]
    assert order["final_total"] == 500.0
    assert order["items"][0]["unit_price"] == 100.0

    # 3. Change Product Price in Catalog
    price_change = logged_in_client_a.put(f"/api/catalog/products/{p_id}", json={"current_price": 250.0})
    assert price_change.status_code == 200

    # 4. Fetch Order again - price must remain 100.0
    fetch_resp = logged_in_client_a.get(f"/api/orders/{order['id']}")
    fetched_order = fetch_resp.get_json()["order"]
    assert fetched_order["items"][0]["unit_price"] == 100.0
    assert fetched_order["final_total"] == 500.0


def test_snapshot_survives_product_deletion(logged_in_client_a):
    """Deleting a product from the catalog must not affect orders already
    placed against it — they hold a copy, not a foreign key."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Doomed Product", "sku": "D1", "current_price": 20.0,
    }).get_json()["product"]["id"]

    o_resp = logged_in_client_a.post("/api/orders", json={
        "supplier_id": s_id, "items": [{"product_id": p_id, "quantity": 3}],
    })
    order_id = o_resp.get_json()["order"]["id"]

    deleted = logged_in_client_a.delete(f"/api/catalog/products/{p_id}")
    assert deleted.status_code == 200
    assert logged_in_client_a.get(f"/api/catalog/products/{p_id}").status_code == 404

    fetched_order = logged_in_client_a.get(f"/api/orders/{order_id}").get_json()["order"]
    assert fetched_order["items"][0]["product_name"] == "Doomed Product"
    assert fetched_order["items"][0]["unit_price"] == 20.0
    assert fetched_order["final_total"] == 60.0


def test_employee_cannot_update_product(client_a, tenant_a_admin):
    from test_security import _register_employee  # noqa: local import to reuse the helper

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    s_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "P", "sku": "P1", "current_price": 1.0,
    }).get_json()["product"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.put(f"/api/catalog/products/{p_id}", json={"current_price": 999.0})
    assert resp.status_code == 403


def test_audit_log_for_catalog_actions(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Audit Test"})
    resp = logged_in_client_a.get("/api/audit")
    logs = resp.get_json()["logs"]
    actions = [log["action"] for log in logs]
    assert "catalog.supplier_created" in actions
