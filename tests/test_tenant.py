"""Multi-tenant isolation: the core security property of the whole platform."""


def test_tenant_a_cannot_see_tenant_b_orders(logged_in_client_a, logged_in_client_b, make_order):
    resp_a, _, _ = make_order(logged_in_client_a, supplier_name="Only A can see this")
    assert resp_a.status_code == 201

    resp_b = logged_in_client_b.get("/api/orders")
    assert resp_b.status_code == 200
    suppliers = [o["supplier_name"] for o in resp_b.get_json()["orders"]]
    assert "Only A can see this" not in suppliers


def test_tenant_b_cannot_fetch_tenant_a_order_by_id(logged_in_client_a, logged_in_client_b, make_order):
    resp_a, _, _ = make_order(logged_in_client_a)
    order_id = resp_a.get_json()["order"]["id"]

    resp_b = logged_in_client_b.get(f"/api/orders/{order_id}")
    assert resp_b.status_code == 404


def test_tenant_b_cannot_update_tenant_a_order(logged_in_client_a, logged_in_client_b, make_order):
    resp_a, _, _ = make_order(logged_in_client_a)
    order_id = resp_a.get_json()["order"]["id"]

    resp_b = logged_in_client_b.put(f"/api/orders/{order_id}", json={"notes": "hijacked"})
    assert resp_b.status_code == 404


def test_tenant_b_cannot_delete_tenant_a_order(logged_in_client_a, logged_in_client_b, make_order):
    resp_a, _, _ = make_order(logged_in_client_a)
    order_id = resp_a.get_json()["order"]["id"]

    resp_b = logged_in_client_b.delete(f"/api/orders/{order_id}")
    assert resp_b.status_code == 404


def test_tenant_b_cannot_submit_tenant_a_order(logged_in_client_a, logged_in_client_b, make_order):
    resp_a, _, _ = make_order(logged_in_client_a)
    order_id = resp_a.get_json()["order"]["id"]

    resp_b = logged_in_client_b.post(f"/api/orders/{order_id}/submit")
    assert resp_b.status_code == 404


def test_tenant_b_cannot_see_tenant_a_products(logged_in_client_a, logged_in_client_b, make_order):
    _, _, product_id = make_order(logged_in_client_a, product_name="A-only Product")

    resp_b = logged_in_client_b.get("/api/catalog/products")
    names = [p["name"] for p in resp_b.get_json()["products"]]
    assert "A-only Product" not in names

    direct = logged_in_client_b.get(f"/api/catalog/products/{product_id}")
    assert direct.status_code == 404


def test_tenant_b_cannot_see_tenant_a_audit_logs(logged_in_client_a, logged_in_client_b, make_order):
    make_order(logged_in_client_a, supplier_name="Secret Supplier")

    resp_b = logged_in_client_b.get("/api/audit")
    assert resp_b.status_code == 200
    titles = [log["title"] for log in resp_b.get_json()["logs"]]
    assert not any("Secret Supplier" in (t or "") for t in titles)


def test_tenant_b_notifications_isolated_from_tenant_a(logged_in_client_a, logged_in_client_b):
    logged_in_client_a.post("/api/notifications", json={"title": "A-only notice"})

    resp_b = logged_in_client_b.get("/api/notifications")
    titles = [n["title"] for n in resp_b.get_json()["notifications"]]
    assert "A-only notice" not in titles


def test_registering_second_tenant_gets_distinct_tenant_id(tenant_a_admin, tenant_b_admin):
    data_a, _ = tenant_a_admin
    data_b, _ = tenant_b_admin
    assert data_a["tenant"]["id"] != data_b["tenant"]["id"]
