def test_existing_tenant_registration_cannot_self_assign_admin(client):
    first = client.post("/api/auth/register", json={
        "email": "owner@role.test",
        "password": "Passw0rd1",
        "full_name": "Owner",
        "tenant_name": "Role Co",
    })
    assert first.status_code == 201
    slug = first.get_json()["tenant"]["slug"]

    joined = client.post("/api/auth/register", json={
        "email": "attacker@role.test",
        "password": "Passw0rd1",
        "full_name": "Attacker",
        "tenant_slug": slug,
        "role": "admin",
    })
    assert joined.status_code == 201
    assert joined.get_json()["user"]["role"] == "employee"


def test_login_requires_tenant_when_email_exists_in_multiple_tenants(client):
    a = client.post("/api/auth/register", json={
        "email": "same@example.test",
        "password": "Passw0rd1",
        "full_name": "Same A",
        "tenant_name": "Tenant A",
    })
    b = client.post("/api/auth/register", json={
        "email": "same@example.test",
        "password": "Passw0rd1",
        "full_name": "Same B",
        "tenant_name": "Tenant B",
    })
    assert a.status_code == 201
    assert b.status_code == 201

    ambiguous = client.post("/api/auth/login", json={
        "email": "same@example.test",
        "password": "Passw0rd1",
    })
    assert ambiguous.status_code == 409
    assert ambiguous.get_json()["error"] == "tenant_required"

    slug = a.get_json()["tenant"]["slug"]
    selected = client.post("/api/auth/login", json={
        "email": "same@example.test",
        "password": "Passw0rd1",
        "tenant_slug": slug,
    })
    assert selected.status_code == 200
    assert selected.get_json()["tenant"]["slug"] == slug


def test_inactive_tenant_invalidates_existing_session(logged_in_client_a, db):
    from app.models.tenant import Tenant

    me = logged_in_client_a.get("/api/auth/me")
    assert me.status_code == 200
    tenant_id = me.get_json()["user"]["tenant_id"]

    tenant = db.session.get(Tenant, tenant_id)
    tenant.active = False
    db.session.commit()

    assert logged_in_client_a.get("/api/auth/me").status_code == 401


def test_inactive_user_invalidates_existing_session(logged_in_client_a, db):
    from app.models.user import User

    me = logged_in_client_a.get("/api/auth/me")
    assert me.status_code == 200
    user_id = me.get_json()["user"]["id"]

    user = db.session.get(User, user_id)
    user.active = False
    db.session.commit()

    assert logged_in_client_a.get("/api/auth/me").status_code == 401


def test_order_creator_cannot_approve_own_order(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    assert resp.status_code == 201
    order_id = resp.get_json()["order"]["id"]

    assert logged_in_client_a.post(f"/api/orders/{order_id}/submit").status_code == 200
    blocked = logged_in_client_a.post(f"/api/orders/{order_id}/approve")
    assert blocked.status_code == 409
    assert "creator" in blocked.get_json()["message"].lower()


def test_invalid_order_quantities_are_rejected(logged_in_client_a, make_order):
    for quantity in (0, -1, 100001, "abc"):
        resp, _, _ = make_order(logged_in_client_a, quantity=quantity, sku=f"SKU-{quantity}")
        assert resp.status_code == 400, (quantity, resp.get_json())


def test_employee_cannot_edit_another_users_draft(logged_in_client_a, tenant_a_admin, make_order):
    tenant_data, _ = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]

    first, _, _ = make_order(logged_in_client_a, product_name="Protected Draft")
    assert first.status_code == 201
    order_id = first.get_json()["order"]["id"]

    logged_in_client_a.post("/api/auth/logout")
    register = logged_in_client_a.post("/api/auth/register", json={
        "email": "second.employee@acme.test",
        "password": "Passw0rd1",
        "full_name": "Second Employee",
        "tenant_slug": slug,
    })
    assert register.status_code == 201
    logged_in_client_a.post("/api/auth/login", json={
        "email": "second.employee@acme.test", "password": "Passw0rd1"
    })

    blocked = logged_in_client_a.put(f"/api/orders/{order_id}", json={"notes": "hijacked"})
    assert blocked.status_code == 409


def test_employee_cannot_submit_another_users_draft(logged_in_client_a, tenant_a_admin, make_order):
    tenant_data, _ = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]

    first, _, _ = make_order(logged_in_client_a, product_name="Protected Submit")
    assert first.status_code == 201
    order_id = first.get_json()["order"]["id"]

    logged_in_client_a.post("/api/auth/logout")
    register = logged_in_client_a.post("/api/auth/register", json={
        "email": "third.employee@acme.test",
        "password": "Passw0rd1",
        "full_name": "Third Employee",
        "tenant_slug": slug,
    })
    assert register.status_code == 201
    logged_in_client_a.post("/api/auth/login", json={
        "email": "third.employee@acme.test", "password": "Passw0rd1"
    })

    blocked = logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    assert blocked.status_code == 409


def test_order_creator_cannot_reject_own_order(logged_in_client_a, make_order):
    first, _, _ = make_order(logged_in_client_a, product_name="Own Reject")
    assert first.status_code == 201
    order_id = first.get_json()["order"]["id"]
    assert logged_in_client_a.post(f"/api/orders/{order_id}/submit").status_code == 200

    blocked = logged_in_client_a.post(f"/api/orders/{order_id}/reject", json={"reason": "self reject"})
    assert blocked.status_code == 409
    assert "creator" in blocked.get_json()["message"].lower()
