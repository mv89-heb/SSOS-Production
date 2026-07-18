import pytest

from app import create_app
from app.extensions import db as _db
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()

    # IMPORTANT: do not hold an app context open across the yield. Since Flask 2.2,
    # flask.g (where Flask-Login caches the resolved current_user) is scoped to the
    # app context, not the request. If a single app context stayed open for the
    # whole test, every test_client() request reusing it would inherit whichever
    # user Flask-Login last resolved into g — silently leaking identity between
    # two otherwise-independent test clients (e.g. tenant-isolation tests). Leaving
    # no app context active here means each request pushes and pops its own.
    yield application

    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


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
    """Registers a brand-new tenant ('Acme Co') and returns (response-json, credentials)."""
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
    """
    Factory fixture: creates a supplier + product via the Catalog API on the
    given client, then creates an order against that product. Returns the
    raw `/api/orders` POST response so callers can assert on status code or
    pull the order out of the body themselves.

    Order creation only accepts supplier_id/product_id (Snapshot
    Architecture reads prices from the catalog) — this factory exists so
    every test that needs an order doesn't have to repeat the two catalog
    calls first.
    """
    def _make(client, quantity=1, price=10.0, supplier_name="Test Supplier", product_name="Test Product", sku="SKU-TEST"):
        s = client.post("/api/catalog/suppliers", json={"name": supplier_name})
        supplier_id = s.get_json()["supplier"]["id"]
        p = client.post("/api/catalog/products", json={
            "supplier_id": supplier_id, "name": product_name, "sku": sku, "current_price": price,
        })
        product_id = p.get_json()["product"]["id"]
        resp = client.post("/api/orders", json={
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": quantity}],
        })
        return resp, supplier_id, product_id
    return _make
