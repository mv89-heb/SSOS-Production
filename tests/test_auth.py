def test_register_creates_tenant_and_admin_user(client):
    resp = client.post("/api/auth/register", json={
        "email": "founder@newco.test", "password": "Passw0rd1",
        "full_name": "Founder", "tenant_name": "NewCo",
    })
    data = resp.get_json()
    assert resp.status_code == 201
    assert data["user"]["role"] == "admin"
    assert data["tenant"]["slug"] == "newco"


def test_register_rejects_weak_password(client):
    resp = client.post("/api/auth/register", json={
        "email": "a@newco.test", "password": "weak",
        "full_name": "A", "tenant_name": "NewCo2",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "weak_password"


def test_register_rejects_invalid_email(client):
    resp = client.post("/api/auth/register", json={
        "email": "not-an-email", "password": "Passw0rd1",
        "full_name": "A", "tenant_name": "NewCo3",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_email"


def test_register_duplicate_tenant_name_rejected(client):
    client.post("/api/auth/register", json={
        "email": "one@dupco.test", "password": "Passw0rd1",
        "full_name": "One", "tenant_name": "DupCo",
    })
    resp = client.post("/api/auth/register", json={
        "email": "two@dupco.test", "password": "Passw0rd1",
        "full_name": "Two", "tenant_name": "DupCo",
    })
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "tenant_already_exists"


def test_second_user_can_join_existing_tenant_by_slug(client):
    reg1 = client.post("/api/auth/register", json={
        "email": "admin@joinco.test", "password": "Passw0rd1",
        "full_name": "Admin", "tenant_name": "JoinCo",
    })
    slug = reg1.get_json()["tenant"]["slug"]
    resp = client.post("/api/auth/register", json={
        "email": "emp@joinco.test", "password": "Passw0rd1",
        "full_name": "Employee", "tenant_slug": slug, "role": "employee",
    })
    assert resp.status_code == 201
    assert resp.get_json()["user"]["role"] == "employee"
    assert resp.get_json()["user"]["tenant_id"] == reg1.get_json()["tenant"]["id"]


def test_login_success(client, tenant_a_admin, client_a):
    _, creds = tenant_a_admin
    resp = client_a.post("/api/auth/login", json=creds)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_login_wrong_password_fails(client_a, tenant_a_admin):
    resp = client_a.post("/api/auth/login", json={"email": "admin@acme.test", "password": "WrongPass1"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_credentials"


def test_login_unknown_email_fails(client):
    resp = client.post("/api/auth/login", json={"email": "nobody@nowhere.test", "password": "Passw0rd1"})
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "a@b.com"})
    assert resp.status_code == 400


def test_me_requires_login(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(logged_in_client_a):
    resp = logged_in_client_a.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "admin@acme.test"


def test_logout(logged_in_client_a):
    resp = logged_in_client_a.post("/api/auth/logout")
    assert resp.status_code == 200
    followup = logged_in_client_a.get("/api/auth/me")
    assert followup.status_code == 401

# --- CSRF protection (production config) -----------------------------------
# The default `client`/`app` fixtures use TestingConfig, which disables CSRF
# entirely — so a regression here (e.g. an unprotected mutating route, or the
# frontend forgetting to send the token) would never show up in the rest of
# this suite. These tests spin up a second app instance with CSRF actually
# enabled, matching render.yaml's production config, to close that gap.


def _csrf_enabled_client():
    import os
    from app import create_app
    from app.extensions import db

    os.environ["WTF_CSRF_ENABLED"] = "True"
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        db.create_all()
    client = app.test_client()
    return app, client


def test_login_without_csrf_token_is_rejected_when_csrf_enabled():
    app, client = _csrf_enabled_client()
    try:
        client.post("/api/auth/register", json={
            "email": "csrf@acme.test", "password": "Passw0rd1",
            "full_name": "CSRF Test", "tenant_name": "CSRF Co",
        })
        resp = client.post("/api/auth/login", json={
            "email": "csrf@acme.test", "password": "Passw0rd1",
        })
        assert resp.status_code == 400
        assert "csrf" in resp.get_json()["message"].lower()
    finally:
        with app.app_context():
            from app.extensions import db
            db.session.remove()
            db.drop_all()


def test_login_with_csrf_token_succeeds_when_csrf_enabled():
    app, client = _csrf_enabled_client()
    try:
        token = client.get("/api/auth/csrf-token").get_json()["csrf_token"]
        client.post(
            "/api/auth/register",
            json={"email": "csrf2@acme.test", "password": "Passw0rd1",
                  "full_name": "CSRF Test 2", "tenant_name": "CSRF Co 2"},
            headers={"X-CSRFToken": token},
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": "csrf2@acme.test", "password": "Passw0rd1"},
            headers={"X-CSRFToken": token},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        assert "session=" in resp.headers.get("Set-Cookie", "")
    finally:
        with app.app_context():
            from app.extensions import db
            db.session.remove()
            db.drop_all()
