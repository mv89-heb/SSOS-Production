from app.models.supplier_invoice import (
    INVOICE_APPROVAL_APPROVED,
    INVOICE_APPROVAL_PENDING,
    VALID_INVOICE_APPROVAL_STATUSES,
)


def _create_sent_order(client, make_order):
    response, _, _ = make_order(client)
    assert response.status_code in (200, 201), response.get_json()
    order_id = response.get_json()["order"]["id"]
    for action in ("submit", "approve", "sent"):
        response = client.post(f"/api/orders/{order_id}/{action}", json={})
        assert response.status_code == 200, response.get_json()
    return order_id


def test_invoice_approval_status_constants_are_explicit():
    assert INVOICE_APPROVAL_PENDING == "pending_approval"
    assert INVOICE_APPROVAL_APPROVED == "approved_for_payment"
    assert VALID_INVOICE_APPROVAL_STATUSES == (
        "pending_approval",
        "approved_for_payment",
    )


def test_invoice_payment_requires_manager_approval_and_audit(logged_in_client_a, make_order, db):
    client = logged_in_client_a
    order_id = _create_sent_order(client, make_order)
    created = client.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "INV-APPROVAL-001", "amount": 10},
    )
    assert created.status_code == 201, created.get_json()
    invoice = created.get_json()["invoice"]
    invoice_id = invoice["id"]
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

    reset = client.post(
        f"/api/supplier-invoices/{invoice_id}/approval",
        json={"approval_status": INVOICE_APPROVAL_PENDING},
    )
    assert reset.status_code == 409
