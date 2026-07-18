import uuid


def _create_order(client, supplier="Supplier X"):
    """Creates a supplier + product via the Catalog API, then an order against
    them. The Orders API only accepts supplier_id/product_id (Snapshot
    Architecture freezes catalog prices), so a raw supplier_name payload is
    rejected. SKU is randomized so repeated calls don't collide."""
    s = client.post("/api/catalog/suppliers", json={"name": supplier})
    supplier_id = s.get_json()["supplier"]["id"]
    p = client.post("/api/catalog/products", json={
        "supplier_id": supplier_id,
        "name": "Audit Item",
        "sku": f"SKU-{uuid.uuid4().hex[:8]}",
        "current_price": 5,
    })
    product_id = p.get_json()["product"]["id"]
    resp = client.post("/api/orders", json={
        "supplier_id": supplier_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert resp.status_code == 201, resp.get_json()
    return resp


def test_actions_generate_audit_entries(logged_in_client_a):
    _create_order(logged_in_client_a)
    resp = logged_in_client_a.get("/api/audit")
    assert resp.status_code == 200
    actions = [log["action"] for log in resp.get_json()["logs"]]
    assert "order.created" in actions
    assert "auth.login" in actions
    assert "auth.register" in actions


def test_audit_chain_verifies_as_valid(logged_in_client_a):
    _create_order(logged_in_client_a)
    _create_order(logged_in_client_a, supplier="Supplier Y")
    resp = logged_in_client_a.get("/api/audit/verify")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["valid"] is True
    assert body["first_broken_log_id"] is None


def test_audit_entries_are_hash_chained(logged_in_client_a):
    _create_order(logged_in_client_a)
    _create_order(logged_in_client_a, supplier="Supplier Z")
    logs = logged_in_client_a.get("/api/audit").get_json()["logs"]
    # logs are returned newest-first; verify adjacent linkage
    ordered = sorted(logs, key=lambda x: x["id"])
    for i in range(1, len(ordered)):
        assert ordered[i]["previous_hash"] == ordered[i - 1]["hash_chain"]


def test_tampering_audit_log_breaks_verification(app, logged_in_client_a, db):
    from app.models.audit import AuditLog

    _create_order(logged_in_client_a)
    with app.app_context():
        log = db.session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        log_id = log.id
        # Bypass the ORM event listener to simulate direct tampering (e.g. a rogue DBA)
        db.session.execute(
            db.update(AuditLog).where(AuditLog.id == log_id).values(title="TAMPERED")
        )
        db.session.commit()

    resp = logged_in_client_a.get("/api/audit/verify")
    body = resp.get_json()
    assert body["valid"] is False
    assert body["first_broken_log_id"] == log_id


def test_audit_update_via_orm_is_blocked(app, db):
    from app.models.audit import AuditLog
    from app.services.audit_service import AuditService

    with app.app_context():
        log = AuditService.log_event(tenant_id=1, user_id=None, action="test.action", title="t")
        log.title = "changed"
        try:
            db.session.commit()
            raised = False
        except RuntimeError:
            raised = True
        db.session.rollback()
        assert raised


def test_audit_delete_via_orm_is_blocked(app, db):
    from app.services.audit_service import AuditService

    with app.app_context():
        log = AuditService.log_event(tenant_id=1, user_id=None, action="test.action2", title="t")
        db.session.delete(log)
        try:
            db.session.commit()
            raised = False
        except RuntimeError:
            raised = True
        db.session.rollback()
        assert raised


def test_audit_requires_manager_role(logged_in_client_a, client_a, tenant_a_admin):
    tenant_data, _ = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    reg = client_a.post("/api/auth/register", json={
        "email": "worker@acme.test", "password": "Passw0rd1",
        "full_name": "Worker", "tenant_slug": slug, "role": "employee",
    })
    assert reg.status_code == 201

    worker_client = client_a  # reuse app but log in fresh as worker
    worker_client.post("/api/auth/logout")
    login = worker_client.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})
    assert login.status_code == 200

    resp = worker_client.get("/api/audit")
    assert resp.status_code == 403


def test_audit_verify_requires_login(client):
    resp = client.get("/api/audit/verify")
    assert resp.status_code == 401
