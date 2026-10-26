from app.models.supplier_invoice import (
    INVOICE_APPROVAL_APPROVED,
    INVOICE_APPROVAL_PENDING,
    VALID_INVOICE_APPROVAL_STATUSES,
)


def _create_order(client, make_order):
    response, _, _ = make_order(client)
    assert response.status_code in (200, 201), response.get_json()
    return response.get_json()["order"]["id"]


def test_invoice_approval_status_constants_are_explicit():
    assert INVOICE_APPROVAL_PENDING == "pending_approval"
    assert INVOICE_APPROVAL_APPROVED == "approved_for_payment"
    assert VALID_INVOICE_APPROVAL_STATUSES == (
        "pending_approval",
        "approved_for_payment",
    )


def test_invoice_payment_requires_manager_approval_and_audit(logged_in_client_a, make_order, db):
    client = logged_in_client_a
    order_id = _create_order(client, make_order)
    created = client.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "INV-APPROVAL-001", "amount": 10},
    )
    assert created.status_code == 201, created.get_json()
    invoice = created.get_json()["invoice"]
    invoice_id = invoice["id"]
    from app.models.audit import AuditLog
    creation_event = db.session.query(AuditLog).filter_by(
        action="supplier_invoice.created"
    ).first()
    assert creation_event is not None
    assert creation_event.metadata_json["invoice_id"] == invoice_id
    duplicate = client.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "INV-APPROVAL-001", "amount": 10},
    )
    assert duplicate.status_code == 409, duplicate.get_json()
    assert "already exists" in duplicate.get_json()["message"].lower()
    assert invoice["approval_status"] == INVOICE_APPROVAL_PENDING

    payment = client.post(
        f"/api/supplier-invoices/{invoice_id}/payments",
        json={"amount": 10, "payment_date": "2026-10-25"},
    )
    assert payment.status_code == 409
    assert "approved" in payment.get_json()["message"].lower()

    approved = client.post(
        f"/api/supplier-invoices/{invoice_id}/approval",
        json={"approval_status": INVOICE_APPROVAL_APPROVED},
    )
    assert approved.status_code == 200, approved.get_json()
    approved_invoice = approved.get_json()["invoice"]
    assert approved_invoice["approval_status"] == INVOICE_APPROVAL_APPROVED
    assert approved_invoice["approved_by"] is not None
    assert approved_invoice["approved_at"] is not None

    payment = client.post(
        f"/api/supplier-invoices/{invoice_id}/payments",
        json={"amount": 10, "payment_date": "2026-10-25", "reference": "TEST-TRANSFER"},
    )
    assert payment.status_code == 201, payment.get_json()
    assert payment.get_json()["invoice"]["status"] == "paid"
    payment_event = db.session.query(AuditLog).filter_by(
        action="supplier_invoice.payment_recorded"
    ).first()
    assert payment_event is not None
    assert payment_event.metadata_json["invoice_id"] == invoice_id
    assert payment_event.metadata_json["fully_paid"] is True

    reset = client.post(
        f"/api/supplier-invoices/{invoice_id}/approval",
        json={"approval_status": INVOICE_APPROVAL_PENDING},
    )
    assert reset.status_code == 409



def test_invoice_list_requires_orders_view_permission(logged_in_client_a, tenant_a_admin, make_order, db):
    client = logged_in_client_a
    tenant_data, _ = tenant_a_admin
    tenant_slug = tenant_data["tenant"]["slug"]
    order_id = _create_order(client, make_order)
    created = client.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "INV-READ-PERM-001", "amount": 25},
    )
    assert created.status_code == 201, created.get_json()

    registered = client.post("/api/auth/register", json={
        "email": "invoice-reader@acme.test",
        "password": "Passw0rd1",
        "full_name": "Invoice Reader",
        "tenant_slug": tenant_slug,
        "role": "employee",
    })
    assert registered.status_code in (200, 201), registered.get_json()
    from app.models.user import User
    employee = db.session.query(User).filter_by(
        tenant_id=tenant_data["tenant"]["id"],
        email="invoice-reader@acme.test",
    ).first()
    assert employee is not None
    employee.permissions = {"orders.view": False}
    db.session.commit()

    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={
        "email": "invoice-reader@acme.test",
        "password": "Passw0rd1",
    })
    assert login.status_code == 200, login.get_json()
    denied = client.get(f"/api/orders/{order_id}/invoices")
    assert denied.status_code == 403, denied.get_json()
