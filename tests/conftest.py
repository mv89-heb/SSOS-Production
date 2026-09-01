import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()

    yield application

    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    # Some legacy tests intentionally exercise ORM operations directly.
    # Keep the context scoped to the fixture so those operations have a
    # valid Flask application context without changing request isolation.
    with app.app_context():
        yield _db


def _register(client, tenant_name, email, password="Passw0rd1", full_name="Test User", tenant_slug=None):
    payload = {
        "email": email,
        "password": password,
        "full_name": full_name,
        "tenant_name": tenant_name,
    }
    if tenant_slug:
        payload = {"email": email, "password": password, "full_name": full_name, "tenant_slug": tenant_slug}
    return client.post("/api/auth/register", json=payload)


@pytest.fixture()
def client_a(app):
    return app.test_client()


@pytest.fixture()
def client_b(app):
    return app.test_client()


@pytest.fixture()
def tenant_a_admin(client_a):
    resp = _register(client_a, tenant_name="Acme Co", email="admin@acme.test")
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json(), {"email": "admin@acme.test", "password": "Passw0rd1"}


@pytest.fixture()
def tenant_b_admin(client_b):
    resp = _register(client_b, tenant_name="Beta Inc", email="admin@beta.test")
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json(), {"email": "admin@beta.test", "password": "Passw0rd1"}


@pytest.fixture()
def logged_in_client_a(client_a, tenant_a_admin):
    _, creds = tenant_a_admin
    resp = client_a.post("/api/auth/login", json=creds)
    assert resp.status_code == 200
    return client_a


@pytest.fixture()
def logged_in_client_b(client_b, tenant_b_admin):
    _, creds = tenant_b_admin
    resp = client_b.post("/api/auth/login", json=creds)
    assert resp.status_code == 200
    return client_b


def register_employee(client, tenant_slug, email="employee@acme.test"):
    return _register(client, tenant_name=None, email=email, tenant_slug=tenant_slug, full_name="Employee One")


@pytest.fixture()
def make_order():
    def _make(client, quantity=1, price=10.0, supplier_name="Test Supplier", product_name="Test Product", sku="SKU-TEST"):
        s = client.post("/api/catalog/suppliers", json={"name": supplier_name})
        supplier_id = s.get_json()["supplier"]["id"]
        p = client.post("/api/catalog/products", json={
            "supplier_id": supplier_id, "name": product_name, "sku": sku, "current_price": price,
        })
        # SKU is a tenant-level product identity. A number of legacy lifecycle
        # tests create separate suppliers with the same helper defaults, so
        # retry with a deterministic suffix rather than masking the catalog
        # uniqueness rule.
        if p.status_code != 201:
            retry_sku = f"{sku}-{supplier_id}"
            p = client.post("/api/catalog/products", json={
                "supplier_id": supplier_id, "name": product_name, "sku": retry_sku, "current_price": price,
            })
        assert p.status_code == 201, p.get_json()
        product_id = p.get_json()["product"]["id"]
        resp = client.post("/api/orders", json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": quantity}],
        })
        return resp, supplier_id, product_id
    return _make
