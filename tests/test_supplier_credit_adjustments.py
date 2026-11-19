from app.models.audit import AuditLog
from app.models.supplier_credit_adjustment import (
    CREDIT_ADJUSTMENT_ACTIVE,
    CREDIT_ADJUSTMENT_VOIDED,
)
from app.models.supplier_invoice import SupplierInvoice


def _create_order(client, make_order, **kwargs):
    response, _, _ = make_order(client, **kwargs)
    assert response.status_code in (200, 201), response.get_json()
    return response.get_json()["order"]["id"]


def test_supplier_credit_adjustment_is_linked_audited_and_does_not_change_invoice_balance(
    logged_in_client_a, make_order, db
):
    client = logged_in_client_a
    order_id = _create_order(client, make_order, supplier_name="Credit Supplier", sku="CREDIT-001")
    invoice_response = client.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "CREDIT-INVOICE-001", "amount": 100, "currency": "ILS"},
    )
    assert invoice_response.status_code == 201, invoice_response.get_json()
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    created = client.post(
        f"/api/orders/{order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-NOTE-001",
            "adjustment_type": "credit_note",
            "adjustment_date": "2026-11-12",
            "amount": "15.50",
            "invoice_id": invoice_id,
            "reason": "זיכוי בגין חוסר בפריטים",
            "currency": "ILS",
        },
    )
    assert created.status_code == 201, created.get_json()
    adjustment = created.get_json()["credit_adjustment"]
    assert adjustment["status"] == CREDIT_ADJUSTMENT_ACTIVE
    assert adjustment["invoice_id"] == invoice_id
    assert adjustment["amount"] == 15.5

    listed = client.get(f"/api/orders/{order_id}/credit-adjustments")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()["credit_adjustments"]] == [adjustment["id"]]

    invoice = db.session.get(SupplierInvoice, invoice_id)
    assert float(invoice.amount) == 100.0
    assert invoice.to_dict()["balance"] == 100.0

    duplicate = client.post(
        f"/api/orders/{order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-NOTE-001",
            "adjustment_type": "credit_note",
            "adjustment_date": "2026-11-12",
            "amount": 15,
            "currency": "ILS",
        },
    )
    assert duplicate.status_code == 409

    event = db.session.query(AuditLog).filter_by(
        action="supplier_credit_adjustment.created"
    ).first()
    assert event is not None
    assert event.metadata_json["credit_adjustment_id"] == adjustment["id"]


def test_supplier_credit_adjustment_void_is_audited_and_excluded_from_active_status(
    logged_in_client_a, make_order, db
):
    client = logged_in_client_a
    order_id = _create_order(client, make_order, supplier_name="Void Credit Supplier")
    created = client.post(
        f"/api/orders/{order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-VOID-001",
            "adjustment_type": "price_adjustment",
            "adjustment_date": "2026-11-15",
            "amount": 20,
            "reason": "התאמת מחיר מוסכמת",
        },
    )
    assert created.status_code == 201, created.get_json()
    adjustment_id = created.get_json()["credit_adjustment"]["id"]

    missing_reason = client.post(
        f"/api/supplier-credit-adjustments/{adjustment_id}/void",
        json={"reason": ""},
    )
    assert missing_reason.status_code == 400

    voided = client.post(
        f"/api/supplier-credit-adjustments/{adjustment_id}/void",
        json={"reason": "נרשם בטעות, אסמכתה שגויה"},
    )
    assert voided.status_code == 200, voided.get_json()
    assert voided.get_json()["credit_adjustment"]["status"] == CREDIT_ADJUSTMENT_VOIDED
    assert voided.get_json()["credit_adjustment"]["void_reason"] == "נרשם בטעות, אסמכתה שגויה"

    repeated = client.post(
        f"/api/supplier-credit-adjustments/{adjustment_id}/void",
        json={"reason": "ניסיון ביטול חוזר"},
    )
    assert repeated.status_code == 409

    event = db.session.query(AuditLog).filter_by(
        action="supplier_credit_adjustment.voided"
    ).first()
    assert event is not None
    assert event.metadata_json["credit_adjustment_id"] == adjustment_id


def test_supplier_credit_adjustment_validates_invoice_order_currency_and_tenant(
    logged_in_client_a, logged_in_client_b, make_order
):
    first_order_id = _create_order(logged_in_client_a, make_order, sku="CREDIT-ORDER-A")
    second_order_id = _create_order(logged_in_client_a, make_order, sku="CREDIT-ORDER-B")
    invoice = logged_in_client_a.post(
        f"/api/orders/{second_order_id}/invoices",
        json={"invoice_number": "CREDIT-OTHER-ORDER", "amount": 50},
    )
    assert invoice.status_code == 201
    invoice_id = invoice.get_json()["invoice"]["id"]

    wrong_order_invoice = logged_in_client_a.post(
        f"/api/orders/{first_order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-WRONG-LINK",
            "adjustment_type": "credit_note",
            "adjustment_date": "2026-11-10",
            "amount": 5,
            "invoice_id": invoice_id,
        },
    )
    assert wrong_order_invoice.status_code == 404

    wrong_currency = logged_in_client_a.post(
        f"/api/orders/{first_order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-WRONG-CURRENCY",
            "adjustment_type": "credit_note",
            "adjustment_date": "2026-11-10",
            "amount": 5,
            "currency": "USD",
        },
    )
    assert wrong_currency.status_code == 409

    invalid_amount = logged_in_client_a.post(
        f"/api/orders/{first_order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-NEGATIVE",
            "adjustment_type": "credit_note",
            "adjustment_date": "2026-11-10",
            "amount": -5,
        },
    )
    assert invalid_amount.status_code == 400

    foreign_list = logged_in_client_b.get(
        f"/api/orders/{first_order_id}/credit-adjustments"
    )
    assert foreign_list.status_code == 404

    invalid_type = logged_in_client_a.post(
        f"/api/orders/{first_order_id}/credit-adjustments",
        json={
            "reference_number": "CREDIT-INVALID-TYPE",
            "adjustment_type": "unknown",
            "adjustment_date": "2026-11-10",
            "amount": 5,
        },
    )
    assert invalid_type.status_code == 400
