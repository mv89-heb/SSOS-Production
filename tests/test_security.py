import io


def _register_employee(client, tenant_slug, email="worker@acme.test"):
    return client.post("/api/auth/register", json={
        "email": email, "password": "Passw0rd1", "full_name": "Worker",
        "tenant_slug": tenant_slug, "role": "employee",
    })


def test_password_is_hashed_not_stored_plaintext(app, db, tenant_a_admin):
    from app.models.user import User
    with app.app_context():
        user = db.session.query(User).filter_by(email="admin@acme.test").first()
        assert user.password_hash != "Passw0rd1"
        assert user.check_password("Passw0rd1") is True
        assert user.check_password("WrongPassword1") is False


def test_employee_cannot_delete_orders(client_a, tenant_a_admin, make_order):
    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    # The catalog entries are created as admin (manager+ required), then the
    # employee logs in and attempts the delete.
    client_a.post("/api/auth/login", json=creds)
    create, _, _ = make_order(client_a)
    order_id = create.get_json()["order"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 403


def test_employee_cannot_approve_orders(client_a, tenant_a_admin, make_order):
    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    create, _, _ = make_order(client_a)
    order_id = create.get_json()["order"]["id"]
    client_a.post(f"/api/orders/{order_id}/submit")

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.post(f"/api/orders/{order_id}/approve")
    assert resp.status_code == 403


def test_employee_can_create_orders(client_a, tenant_a_admin):
    tenant_data, _ = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    # Employees can create orders against catalog entries an admin already set up.
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "admin@acme.test", "password": "Passw0rd1"})
    s = client_a.post("/api/catalog/suppliers", json={"name": "Sup"})
    supplier_id = s.get_json()["supplier"]["id"]
    p = client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "P", "sku": "SKU1", "current_price": 1})
    product_id = p.get_json()["product"]["id"]

    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})
    resp = client_a.post("/api/orders", json={
        "supplier_id": supplier_id, "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert resp.status_code == 201


def test_unauthenticated_requests_rejected(client):
    for method, path in [
        ("get", "/api/orders"), ("post", "/api/orders"), ("get", "/api/orders/1"),
        ("put", "/api/orders/1"), ("delete", "/api/orders/1"),
        ("get", "/api/audit"), ("get", "/api/notifications"),
    ]:
        resp = getattr(client, method)(path, json={})
        assert resp.status_code == 401, f"{method} {path} should require auth"


def test_upload_rejects_disallowed_extension(logged_in_client_a, make_order):
    create, _, _ = make_order(logged_in_client_a)
    order_id = create.get_json()["order"]["id"]

    data = {"file": (io.BytesIO(b"not really an executable"), "malware.exe")}
    resp = logged_in_client_a.post(f"/api/orders/{order_id}/ocr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_upload"


def test_upload_requires_a_file(logged_in_client_a, make_order):
    create, _, _ = make_order(logged_in_client_a)
    order_id = create.get_json()["order"]["id"]
    resp = logged_in_client_a.post(f"/api/orders/{order_id}/ocr", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_secure_filename_strips_path_traversal():
    from werkzeug.utils import secure_filename
    assert secure_filename("../../etc/passwd") != "../../etc/passwd"
    assert "/" not in secure_filename("../../etc/passwd.png")


def test_login_rate_limited_after_repeated_failures(client):
    client.post("/api/auth/register", json={
        "email": "ratelimit@acme.test", "password": "Passw0rd1",
        "full_name": "RL", "tenant_name": "RateLimitCo",
    })
    last_status = None
    for _ in range(15):
        resp = client.post("/api/auth/login", json={"email": "ratelimit@acme.test", "password": "wrong"})
        last_status = resp.status_code
    assert last_status == 429


def test_json_error_response_shape_on_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/orders/999999")
    body = resp.get_json()
    assert body["success"] is False
    assert "error" in body


def test_inactive_user_cannot_login(app, db, tenant_a_admin):
    from app.models.user import User
    with app.app_context():
        user = db.session.query(User).filter_by(email="admin@acme.test").first()
        user.active = False
        db.session.commit()

    from app import create_app
    fresh = app.test_client()
    resp = fresh.post("/api/auth/login", json={"email": "admin@acme.test", "password": "Passw0rd1"})
    assert resp.status_code == 401
