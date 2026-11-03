from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order, STATUS_APPROVED, STATUS_DRAFT, STATUS_SENT
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User


def _analysis(db, user, filename, document_type, extracted_data):
    row = DocumentAnalysis(
        tenant_id=user.tenant_id,
        uploaded_by=user.id,
        filename=filename,
        mime_type="application/pdf",
        document_type=document_type,
        status="ANALYZED",
        extracted_data=extracted_data,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_delivery_note_cannot_be_compared_to_draft_order(logged_in_client_a, db, make_order):
    response, _, _ = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    assert order.status == STATUS_DRAFT
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "supplier_matching": {"supplier_id": order.supplier_id, "decision": "AUTO_MATCH"},
        "items": [],
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/compare-order",
        json={"order_id": order.id},
    )
    assert result.status_code == 409, result.get_json()
    assert "valid status" in result.get_json()["message"].lower()


def test_delivery_note_can_be_compared_to_sent_order(logged_in_client_a, db, make_order):
    response, supplier_id, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    order.status = STATUS_SENT
    db.session.commit()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note-sent.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "items": [{
            "description": "Test Product",
            "quantity": 1,
            "unit_price": 10,
            "unit": "יחידה",
            "product_matching": {
                "best_match": {"product_id": product_id, "confidence": 0.99, "decision": "AUTO_MATCH"}
            },
        }],
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/compare-order",
        json={"order_id": order.id},
    )
    assert result.status_code == 200, result.get_json()
    assert result.get_json()["reconciliation"]["supplier_check"] == "MATCH"
    assert result.get_json()["reconciliation"]["lines"][0]["status"] == "MATCH"


def test_invoice_cannot_be_recorded_against_draft_order(logged_in_client_a, db, make_order):
    response, _, _ = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    assert order.status == STATUS_DRAFT
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "invoice-draft.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "document_number": "INV-DRAFT-1",
        "totals": {"total": 100},
        "order_reconciliation": {"order_id": order.id, "supplier_check": "MATCH", "lines": []},
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={"invoice_number": "INV-DRAFT-1", "amount": 100, "allow_price_updates": False},
    )
    assert result.status_code == 409, result.get_json()
    assert SupplierInvoice.query.filter_by(tenant_id=user.tenant_id).count() == 0


def test_invoice_can_be_recorded_against_approved_order_without_price_updates(logged_in_client_a, db, make_order):
    response, _, _ = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    order.status = STATUS_APPROVED
    db.session.commit()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "invoice-approved.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "document_number": "INV-APPROVED-1",
        "totals": {"total": 100},
        "order_reconciliation": {"order_id": order.id, "supplier_check": "MATCH", "lines": []},
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={"invoice_number": "INV-APPROVED-1", "amount": 100, "allow_price_updates": False},
    )
    assert result.status_code == 201, result.get_json()
    invoice = SupplierInvoice.query.filter_by(
        tenant_id=user.tenant_id, invoice_number="INV-APPROVED-1"
    ).one()
    assert invoice.approval_status == "pending_approval"
    assert result.get_json()["automatic_price_updates"] == []
