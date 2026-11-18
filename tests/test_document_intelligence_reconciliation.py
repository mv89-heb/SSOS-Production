from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order, STATUS_APPROVED, STATUS_DRAFT, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.receipt import Receipt
from app.models.receipt_item import ReceiptItem
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



def test_invoice_price_update_requires_posted_receipt_quantity(
    logged_in_client_a, db, make_order
):
    response, _, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    db.session.commit()
    order_item = OrderItem.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id, product_id=product_id
    ).one()
    product = db.session.get(Product, product_id)
    original_price = product.current_price
    invoice_price = float(original_price or 10) + 5
    user = User.query.filter_by(email="admin@acme.test").one()

    analysis = _analysis(db, user, "invoice-before-receipt.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "document_number": "INV-BEFORE-RECEIPT-1",
        "currency": order.currency or "ILS",
        "totals": {"total": invoice_price},
        "items": [{
            "quantity": float(order_item.quantity),
            "unit": product.unit or "יחידה",
            "unit_price": invoice_price,
        }],
        "order_reconciliation": {
            "order_id": order.id,
            "supplier_check": "MATCH",
            "lines": [{
                "line_index": 0,
                "matched": True,
                "status": "REVIEW",
                "order_item_id": order_item.id,
                "product_id": product.id,
                "confidence": 0.99,
                "quantity_delta": 0,
                "flags": ["PRICE_VARIANCE"],
            }],
        },
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-invoice",
        json={
            "invoice_number": "INV-BEFORE-RECEIPT-1",
            "amount": invoice_price * float(order_item.quantity),
            "allow_price_updates": True,
        },
    )
    assert result.status_code == 201, result.get_json()
    db.session.refresh(product)
    assert product.current_price == original_price
    assert result.get_json()["automatic_price_updates"] == []



def test_delivery_note_without_explicit_unit_cannot_post_inventory(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    db.session.commit()
    order_item = OrderItem.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id, product_id=product_id
    ).one()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note-unit-missing.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-UNIT-MISSING-1",
        "items": [{"description": "Test Product", "quantity": 1}],
        "order_reconciliation": {
            "order_id": order.id,
            "supplier_check": "MATCH",
            "lines": [{
                "line_index": 0,
                "matched": True,
                "status": "MATCH",
                "order_item_id": order_item.id,
                "product_id": product_id,
                "confidence": 0.99,
                "flags": [],
            }],
        },
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-delivery-note",
        json={},
    )
    assert result.status_code == 409, result.get_json()
    assert "unit" in result.get_json()["message"].lower()
    assert Receipt.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id
    ).count() == 0



def test_document_reference_text_cannot_be_applied_as_product_line(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    user = User.query.filter_by(email="admin@acme.test").one()
    product = db.session.get(Product, product_id)
    original_price = product.current_price
    analysis = _analysis(db, user, "invoice-reference-text.pdf", "INVOICE", {
        "document_type": "INVOICE",
        "items": [{
            "description": "תעודת משלוח מספר 90190 מיום 15/10/2026",
            "quantity": 1,
            "page_number": 1,
        }],
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply",
        json={"lines": [{
            "line_index": 0,
            "product_id": product_id,
            "supplier_id": supplier_id,
            "price": 8,
            "update_price": True,
        }]},
    )

    assert result.status_code == 400, result.get_json()
    assert "no product-row evidence" in result.get_json()["message"].lower()
    db.session.refresh(product)
    assert product.current_price == original_price
    db.session.refresh(analysis)
    assert analysis.extracted_data.get("applied_line_indexes", []) == []



def test_delivery_note_uses_corrected_document_date_for_receipt(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(logged_in_client_a)
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    db.session.commit()
    order_item = OrderItem.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id, product_id=product_id
    ).one()
    product = db.session.get(Product, product_id)
    product.unit = product.unit or "יחידה"
    db.session.commit()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note-dated.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-DATED-001",
        "document_date": "2026-11-07",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "items": [{
            "description": "Test Product",
            "quantity": 1,
            "unit": product.unit or "יחידה",
        }],
        "order_reconciliation": {
            "order_id": order.id,
            "supplier_check": "MATCH",
            "lines": [{
                "line_index": 0,
                "matched": True,
                "status": "MATCH",
                "order_item_id": order_item.id,
                "product_id": product_id,
                "confidence": 0.99,
                "flags": [],
            }],
        },
    })

    result = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-delivery-note",
        json={},
    )
    assert result.status_code == 201, result.get_json()
    receipt = Receipt.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id
    ).one()
    assert receipt.receipt_number == "DN-DATED-001"
    assert receipt.received_at.date().isoformat() == "2026-11-07"


def test_document_metadata_correction_is_tenant_scoped_and_validated(
    logged_in_client_a, logged_in_client_b, db
):
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "metadata-correction.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "document_number": "OLD-NUMBER",
        "document_date": "2026-11-01",
        "items": [],
    })
    corrected = logged_in_client_a.patch(
        f"/api/document-intelligence/{analysis.id}/metadata",
        json={"document_number": "DN-CORRECTED-42", "document_date": "2026-11-08"},
    )
    assert corrected.status_code == 200, corrected.get_json()
    extracted = corrected.get_json()["analysis"]["extracted_data"]
    assert extracted["document_number"] == "DN-CORRECTED-42"
    assert extracted["document_date"] == "2026-11-08"

    invalid = logged_in_client_a.patch(
        f"/api/document-intelligence/{analysis.id}/metadata",
        json={"document_date": "2026-13-45"},
    )
    assert invalid.status_code == 400

    hidden = logged_in_client_b.patch(
        f"/api/document-intelligence/{analysis.id}/metadata",
        json={"document_number": "CROSS-TENANT"},
    )
    assert hidden.status_code == 404



def test_delivery_note_supports_sequential_partial_receipts_and_blocks_over_receipt(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(
        logged_in_client_a, quantity=5, price=10.0
    )
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    product = db.session.get(Product, product_id)
    product.unit = product.unit or "יחידה"
    product.current_stock = 0
    db.session.commit()
    order_item = OrderItem.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id, product_id=product_id
    ).one()
    user = User.query.filter_by(email="admin@acme.test").one()

    def create_note(number, quantity):
        return _analysis(db, user, f"{number}.pdf", "DELIVERY_NOTE", {
            "document_type": "DELIVERY_NOTE",
            "document_number": number,
            "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
            "items": [{
                "description": "Test Product",
                "quantity": quantity,
                "unit": product.unit,
                "product_matching": {
                    "best_match": {
                        "product_id": product_id,
                        "confidence": 0.99,
                        "decision": "AUTO_MATCH",
                    },
                },
            }],
            "order_reconciliation": None,
        })

    first = create_note("DN-PART-001", 2)
    compared = logged_in_client_a.post(
        f"/api/document-intelligence/{first.id}/compare-order",
        json={"order_id": order.id},
    )
    assert compared.status_code == 200, compared.get_json()
    first_line = compared.get_json()["reconciliation"]["lines"][0]
    assert first_line["expected_quantity"] == 5.0
    assert first_line["status"] == "MATCH"
    assert first_line["flags"] == ["PARTIAL_DELIVERY"]
    assert compared.get_json()["reconciliation"]["review_count"] == 0

    posted_first = logged_in_client_a.post(
        f"/api/document-intelligence/{first.id}/apply-delivery-note",
        json={},
    )
    assert posted_first.status_code == 201, posted_first.get_json()
    assert posted_first.get_json()["receipt"]["items"][0]["quantity"] == 2.0
    assert db.session.get(Product, product_id).current_stock == 2

    second = create_note("DN-PART-002", 3)
    compared_second = logged_in_client_a.post(
        f"/api/document-intelligence/{second.id}/compare-order",
        json={"order_id": order.id},
    )
    assert compared_second.status_code == 200, compared_second.get_json()
    second_line = compared_second.get_json()["reconciliation"]["lines"][0]
    assert second_line["expected_quantity"] == 3.0
    assert second_line["status"] == "MATCH"
    assert second_line["flags"] == []

    posted_second = logged_in_client_a.post(
        f"/api/document-intelligence/{second.id}/apply-delivery-note",
        json={},
    )
    assert posted_second.status_code == 201, posted_second.get_json()
    assert db.session.get(Product, product_id).current_stock == 5

    excess = create_note("DN-OVER-003", 1)
    compared_excess = logged_in_client_a.post(
        f"/api/document-intelligence/{excess.id}/compare-order",
        json={"order_id": order.id},
    )
    assert compared_excess.status_code == 200, compared_excess.get_json()
    excess_line = compared_excess.get_json()["reconciliation"]["lines"][0]
    assert excess_line["expected_quantity"] == 0.0
    assert excess_line["status"] == "REVIEW"
    assert "OVER_RECEIPT" in excess_line["flags"]
    blocked = logged_in_client_a.post(
        f"/api/document-intelligence/{excess.id}/apply-delivery-note",
        json={},
    )
    assert blocked.status_code == 409
    assert db.session.get(Product, product_id).current_stock == 5



def test_manual_delivery_note_line_correction_recalculates_and_posts_with_operator_notes(
    logged_in_client_a, logged_in_client_b, db, make_order
):
    response, supplier_id, product_id = make_order(
        logged_in_client_a, quantity=5, price=10.0
    )
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    product = db.session.get(Product, product_id)
    product.unit = "יחידה"
    product.current_stock = 0
    db.session.commit()
    order_item = OrderItem.query.filter_by(
        tenant_id=order.tenant_id, order_id=order.id, product_id=product_id
    ).one()
    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note-manual-fix.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-MANUAL-FIX-001",
        "document_date": "2026-11-08",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "items": [{
            "description": "Test Product",
            "quantity": None,
            "unit": "קרטון",
            "product_matching": {
                "best_match": {
                    "product_id": product_id,
                    "confidence": 0.99,
                    "decision": "AUTO_MATCH",
                },
            },
        }],
    })

    compared = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/compare-order",
        json={"order_id": order.id},
    )
    assert compared.status_code == 200, compared.get_json()
    assert compared.get_json()["reconciliation"]["review_count"] == 1

    cross_tenant = logged_in_client_b.patch(
        f"/api/document-intelligence/{analysis.id}/delivery-note-lines",
        json={"lines": [{"line_index": 0, "quantity": 2, "unit": "יחידה"}]},
    )
    assert cross_tenant.status_code == 404

    invalid_quantity = logged_in_client_a.patch(
        f"/api/document-intelligence/{analysis.id}/delivery-note-lines",
        json={"lines": [{"line_index": 0, "quantity": 0, "unit": "יחידה"}]},
    )
    assert invalid_quantity.status_code == 400

    corrected = logged_in_client_a.patch(
        f"/api/document-intelligence/{analysis.id}/delivery-note-lines",
        json={
            "lines": [{"line_index": 0, "quantity": 2, "unit": "יחידה"}],
            "notes": "אריזה פגומה בחלק מהאספקה; לבדוק מול הספק",
        },
    )
    assert corrected.status_code == 200, corrected.get_json()
    line = corrected.get_json()["reconciliation"]["lines"][0]
    assert line["status"] == "MATCH"
    assert line["flags"] == ["PARTIAL_DELIVERY"]

    posted = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis.id}/apply-delivery-note",
        json={},
    )
    assert posted.status_code == 201, posted.get_json()
    receipt = Receipt.query.filter_by(order_id=order.id).one()
    assert receipt.items[0].quantity == 2
    assert "אריזה פגומה" in receipt.notes
    saved = db.session.get(DocumentAnalysis, analysis.id)
    assert saved.extracted_data["items"][0]["manual_correction"]["quantity"] is True
    assert saved.extracted_data["items"][0]["manual_correction"]["unit"] is True


def test_delivery_note_order_suggestions_rank_supplier_date_and_explicit_po_reference_without_cross_tenant_data(
    logged_in_client_a, logged_in_client_b, db, make_order
):
    first_response, supplier_id, _ = make_order(
        logged_in_client_a, quantity=4, sku="SUGGEST-OLD", planned_order_date="2026-10-01"
    )
    second_product_response = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Near-date product",
        "sku": "SUGGEST-NEAR", "current_price": 10,
    })
    assert second_product_response.status_code == 201, second_product_response.get_json()
    second_response = logged_in_client_a.post("/api/orders", json={
        "supplier_id": supplier_id,
        "planned_order_date": "2026-11-16",
        "items": [{"product_id": second_product_response.get_json()["product"]["id"], "quantity": 2}],
    })
    other_tenant_response, _, _ = make_order(
        logged_in_client_b, quantity=4, sku="SUGGEST-OTHER-TENANT"
    )
    assert first_response.status_code == second_response.status_code == other_tenant_response.status_code == 201
    first_order = db.session.get(Order, first_response.get_json()["order"]["id"])
    second_order = db.session.get(Order, second_response.get_json()["order"]["id"])
    other_tenant_order = db.session.get(Order, other_tenant_response.get_json()["order"]["id"])
    first_order.status = STATUS_SENT
    second_order.status = STATUS_SENT
    other_tenant_order.status = STATUS_SENT
    db.session.commit()

    user = User.query.filter_by(email="admin@acme.test").one()
    analysis = _analysis(db, user, "delivery-note-suggestions.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-554",
        "purchase_order_number": first_order.order_number,
        "document_date": "2026-11-17",
        "supplier": {"name": "Test Supplier"},
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "items": [],
    })

    result = logged_in_client_a.get(
        f"/api/document-intelligence/{analysis.id}/suggest-orders"
    )
    assert result.status_code == 200, result.get_json()
    payload = result.get_json()
    assert payload["context"]["purchase_order_number"] == first_order.order_number
    assert len(payload["suggestions"]) == 2
    assert payload["suggestions"][0]["order_id"] == first_order.id
    assert payload["suggestions"][0]["purchase_order_number_match"] is True
    assert payload["suggestions"][0]["recommended"] is True
    assert payload["suggestions"][1]["order_id"] == second_order.id
    assert other_tenant_order.id not in {item["order_id"] for item in payload["suggestions"]}


def test_delivery_note_suggestions_exclude_fully_received_orders_and_multi_supplier_documents(
    logged_in_client_a, db, make_order
):
    response, supplier_id, product_id = make_order(logged_in_client_a, quantity=2, sku="SUGGEST-FULL")
    assert response.status_code == 201
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    order_item = OrderItem.query.filter_by(tenant_id=order.tenant_id, order_id=order.id).one()
    receipt = Receipt(
        tenant_id=order.tenant_id,
        order_id=order.id,
        receipt_number="SUGGEST-FULL-RECEIPT",
        status="posted",
    )
    db.session.add(receipt)
    db.session.flush()
    db.session.add(ReceiptItem(
        tenant_id=order.tenant_id,
        receipt_id=receipt.id,
        order_item_id=order_item.id,
        quantity=2,
    ))
    user = User.query.filter_by(email="admin@acme.test").one()
    full_analysis = _analysis(db, user, "fully-received.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "items": [],
    })
    multi_analysis = _analysis(db, user, "multi-supplier-suggestions.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE",
        "supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"},
        "supplier_sections": [
            {"supplier_matching": {"supplier_id": supplier_id, "decision": "AUTO_MATCH"}},
            {"supplier_matching": {"supplier_id": supplier_id + 99999, "decision": "AUTO_MATCH"}},
        ],
        "items": [],
    })
    db.session.commit()

    full_result = logged_in_client_a.get(
        f"/api/document-intelligence/{full_analysis.id}/suggest-orders"
    )
    assert full_result.status_code == 200, full_result.get_json()
    assert full_result.get_json()["suggestions"] == []

    multi_result = logged_in_client_a.get(
        f"/api/document-intelligence/{multi_analysis.id}/suggest-orders"
    )
    assert multi_result.status_code == 200, multi_result.get_json()
    assert multi_result.get_json()["suggestions"] == []
    assert multi_result.get_json()["context"]["multi_supplier_document"] is True


def test_purchase_order_suggestions_are_tenant_scoped_and_require_analyzed_document(
    logged_in_client_a, logged_in_client_b, db, make_order
):
    response, _, _ = make_order(logged_in_client_a, sku="SUGGEST-TENANT")
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_SENT
    user_b = User.query.filter_by(email="admin@beta.test").one()
    analysis_b = _analysis(db, user_b, "tenant-b.pdf", "DELIVERY_NOTE", {
        "document_type": "DELIVERY_NOTE", "items": [],
    })
    db.session.commit()

    inaccessible = logged_in_client_a.get(
        f"/api/document-intelligence/{analysis_b.id}/suggest-orders"
    )
    assert inaccessible.status_code == 404

    user_a = User.query.filter_by(email="admin@acme.test").one()
    uploaded = DocumentAnalysis(
        tenant_id=user_a.tenant_id,
        uploaded_by=user_a.id,
        filename="not-analyzed.pdf",
        mime_type="application/pdf",
        document_type="DELIVERY_NOTE",
        status="UPLOADED",
        extracted_data={"document_type": "DELIVERY_NOTE", "items": []},
    )
    db.session.add(uploaded)
    db.session.commit()
    not_analyzed = logged_in_client_a.get(
        f"/api/document-intelligence/{uploaded.id}/suggest-orders"
    )
    assert not_analyzed.status_code == 400
