from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order, STATUS_APPROVED, STATUS_DRAFT, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
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



def test_multi_supplier_delivery_note_cannot_be_reconciled_to_one_supplier_order(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    order.status = STATUS_SENT
    db.session.commit()
    other_supplier_response = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Other supplier"}
    )
    assert other_supplier_response.status_code == 201, other_supplier_response.get_json()
    other_supplier_id = other_supplier_response.get_json()["supplier"]["id"]
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "multi-supplier-delivery.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "supplier_sections": [
            {"supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"}},
            {"supplier_matching": {"supplier_id": other_supplier_id, "decision": "AUTO_MATCH"}},
        ],
        "items": [{
            "description": "Test Product",
            "quantity": 1,
            "unit_price": 10,
            "unit": "יחידה",
            "supplier_matching": {"supplier_id": other_supplier_id, "decision": "AUTO_MATCH"},
            "product_matching": {
                "best_match": {"product_id": product_id, "confidence": 0.99, "decision": "AUTO_MATCH"}
            },
        }],
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/compare-order",
        json={"order_id": order.id, "confirm_supplier": True},
    )
    assert result.status_code == 200, result.get_json()
    reconciliation = result.get_json()["reconciliation"]
    assert reconciliation["supplier_check"] == "MISMATCH"
    assert reconciliation["unmatched_count"] == 1
    assert reconciliation["lines"][0]["status"] == "SUPPLIER_MISMATCH"


def test_same_analysis_cannot_create_a_second_invoice_with_a_different_number(
    logged_in_client_a, db, make_order
):
    response, _, _ = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    order.status = STATUS_APPROVED
    db.session.commit()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "invoice-retry.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "document_number": "INV-RETRY-1",
        "totals": {"total": 100},
        "order_reconciliation": {"order_id": order.id, "supplier_check": "MATCH", "lines": []},
    })

    first = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={"invoice_number": "INV-RETRY-1", "amount": 100, "allow_price_updates": False},
    )
    assert first.status_code == 201, first.get_json()

    retry = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={"invoice_number": "INV-RETRY-2", "amount": 100, "allow_price_updates": False},
    )
    assert retry.status_code == 409, retry.get_json()
    assert SupplierInvoice.query.filter_by(tenant_id=user.tenant_id).count() == 1

def test_invoice_review_line_never_updates_catalog_price(logged_in_client_a, db, make_order):
    response, _, product_id = make_order(logged_in_client_a, price=10.0)
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    order = db.session.get(Order, order_id)
    order.status = STATUS_APPROVED
    product = db.session.get(Product, product_id)
    product.unit = "יחידה"
    order_item = OrderItem.query.filter_by(order_id=order.id, product_id=product.id).one()
    db.session.commit()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "invoice-review-line.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "document_number": "INV-REVIEW-LINE-1",
        "currency": "ILS",
        "totals": {"total": 12},
        "items": [{"description": "Test Product", "quantity": 1, "unit_price": 12, "unit": "יחידה", "currency": "ILS"}],
        "order_reconciliation": {
            "order_id": order.id,
            "supplier_check": "MATCH",
            "lines": [{
                "line_index": 0, "matched": True, "status": "REVIEW",
                "order_item_id": order_item.id, "confidence": 0.99,
                "flags": ["PRICE_VARIANCE"],
            }],
        },
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={"invoice_number": "INV-REVIEW-LINE-1", "amount": 12, "allow_price_updates": True},
    )
    assert result.status_code == 201, result.get_json()
    db.session.refresh(product)
    assert float(product.current_price) == 10.0
    assert result.get_json()["automatic_price_updates"] == []
