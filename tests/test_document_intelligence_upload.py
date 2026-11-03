from io import BytesIO
from types import SimpleNamespace

from app.models.document_analysis import DocumentAnalysis
from app.models.user import User
from app.services.document_intelligence_service import DocumentIntelligenceService


def test_svg_upload_accepts_browser_octet_stream(logged_in_client_a, monkeypatch):
    def fake_create_analysis(self, filename, storage_path, mime_type):
        assert filename == "invoice.svg"
        assert mime_type == "image/svg+xml"
        return SimpleNamespace(to_dict=lambda: {"filename": filename, "mime_type": mime_type})

    monkeypatch.setattr(
        "app.routes.document_intelligence.DocumentIntelligenceService.create_analysis",
        fake_create_analysis,
    )

    response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"<svg><text>Invoice 123</text></svg>"), "invoice.svg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["analysis"]["mime_type"] == "image/svg+xml"


def test_analyze_deletes_temporary_document(logged_in_client_a, db, monkeypatch):
    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            assert path
            assert progress_callback is not None
            return SimpleNamespace(
                success=True,
                data={"document_type": "INVOICE", "items": [{"description": "Milk", "unit_price": 10}]},
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload_response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake pdf contents"), "invoice.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201, upload_response.get_json()

    analysis_id = upload_response.get_json()["analysis"]["id"]
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row is not None
    temp_path = row.storage_path
    assert temp_path

    analyze_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/analyze")
    assert analyze_response.status_code == 200, analyze_response.get_json()
    assert analyze_response.get_json()["analysis"]["status"] == "ANALYZED"
    routing = analyze_response.get_json()["analysis"]["extracted_data"]["workflow_routing"]
    assert routing["route"] == "INVOICE_RECONCILIATION"
    assert routing["status"] == "NEEDS_REVIEW"
    assert routing["business_data_changed"] is False

    db.session.expire_all()
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row.storage_path is None
    assert not __import__("os").path.exists(temp_path)



def test_rematch_refreshes_saved_analysis_without_calling_gemini(logged_in_client_a, db, monkeypatch):
    calls = {"generate": 0}

    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            calls["generate"] += 1
            return SimpleNamespace(
                success=True,
                data={
                    "document_type": "PRICE_LIST",
                    "supplier": {"name": "Test supplier"},
                    "items": [{"description": "צלחות קטן קרם", "unit_price": 7.5}],
                },
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload_response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake pdf contents"), "price-list.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201, upload_response.get_json()
    analysis_id = upload_response.get_json()["analysis"]["id"]

    analyze_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/analyze")
    assert analyze_response.status_code == 200, analyze_response.get_json()
    assert analyze_response.get_json()["analysis"]["status"] == "ANALYZED"
    assert calls["generate"] == 1

    db.session.expire_all()
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row.storage_path is None
    row.extracted_data = {
        **row.extracted_data,
        "workflow_routing": {"route": "GENERAL_DOCUMENT_REVIEW", "status": "NEEDS_REVIEW"},
    }
    db.session.commit()

    rematch_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/rematch")
    assert rematch_response.status_code == 200, rematch_response.get_json()
    refreshed = rematch_response.get_json()["analysis"]
    assert refreshed["status"] == "ANALYZED"
    assert refreshed["extracted_data"]["matching_version"] == "deterministic-v2-multi-supplier"
    routing = refreshed["extracted_data"]["workflow_routing"]
    assert routing["route"] == "PRICE_LIST_REVIEW"
    assert routing["status"] == "READY_FOR_REVIEW"
    assert calls["generate"] == 1



def test_document_workflow_routing_is_classification_only():
    invoice = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "INVOICE",
        "document_number": "INV-100",
        "supplier": {"name": "ספק לדוגמה"},
        "items": [{"description": "חלב", "quantity": 2}],
    })
    assert invoice["route"] == "INVOICE_RECONCILIATION"
    assert invoice["status"] == "READY_FOR_REVIEW"
    assert invoice["business_data_changed"] is False
    assert invoice["automatic_actions_performed"] == []

    delivery_note = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-200",
        "supplier_sections": [{"supplier": {"name": "ספק לדוגמה"}, "items": [{"description": "לחם"}]}],
        "items": [{"description": "לחם", "quantity": 3}],
    })
    assert delivery_note["route"] == "DELIVERY_NOTE_RECONCILIATION"
    assert delivery_note["status"] == "READY_FOR_REVIEW"

    price_list = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "PRICE_LIST",
        "supplier": {"name": "ספק לדוגמה"},
        "items": [{"description": "אורז", "unit_price": 12}],
    })
    assert price_list["route"] == "PRICE_LIST_REVIEW"
    assert price_list["status"] == "READY_FOR_REVIEW"

    incomplete_invoice = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "INVOICE",
        "supplier": {},
        "items": [],
    })
    assert incomplete_invoice["route"] == "INVOICE_RECONCILIATION"
    assert incomplete_invoice["status"] == "NEEDS_REVIEW"
    assert set(incomplete_invoice["missing_fields"]) == {"זיהוי כל הספקים", "שורות פריטים", "מספר מסמך"}

    supplier_number_only = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "INVOICE",
        "document_number": "INV-250",
        "supplier": {"customer_number": "SUP-77"},
        "items": [{"description": "סוכר"}],
    })
    assert supplier_number_only["supplier_identified"] is True
    assert supplier_number_only["status"] == "READY_FOR_REVIEW"

    multi_supplier_numbers = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "DELIVERY_NOTE",
        "document_number": "DN-250",
        "supplier_sections": [
            {"supplier": {"name": "ספק א"}},
            {"supplier": {"customer_number": "SUP-78"}},
        ],
        "items": [{"description": "קמח"}],
    })
    assert multi_supplier_numbers["supplier_identified"] is True
    assert multi_supplier_numbers["status"] == "READY_FOR_REVIEW"

    partial_multi_supplier = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "INVOICE",
        "document_number": "INV-300",
        "supplier_sections": [
            {"supplier": {"name": "ספק א"}},
            {"supplier": {"name": ""}},
        ],
        "items": [{"description": "קמח"}],
    })
    assert partial_multi_supplier["supplier_identified"] is False
    assert partial_multi_supplier["status"] == "NEEDS_REVIEW"
    assert "זיהוי כל הספקים" in partial_multi_supplier["missing_fields"]

    empty_line = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "PRICE_LIST",
        "supplier": {"name": "ספק"},
        "items": [{}],
    })
    assert empty_line["item_count"] == 0
    assert empty_line["status"] == "NEEDS_REVIEW"

    unknown = DocumentIntelligenceService.build_workflow_routing({
        "document_type": "OTHER",
        "supplier": {"name": "ספק לדוגמה"},
        "items": [{"description": "מסמך"}],
    })
    assert unknown["route"] == "GENERAL_DOCUMENT_REVIEW"
    assert unknown["status"] == "NEEDS_REVIEW"
    assert unknown["status_label"] == "נדרשת בדיקה ידנית"
    assert unknown["missing_fields"] == []



def test_document_analysis_history_is_persistent_and_tenant_scoped(
    logged_in_client_a, logged_in_client_b, db
):
    user_a = User.query.filter_by(email="admin@acme.test").one()
    user_b = User.query.filter_by(email="admin@beta.test").one()
    own = DocumentAnalysis(
        tenant_id=user_a.tenant_id,
        uploaded_by=user_a.id,
        filename="invoice-a.pdf",
        mime_type="application/pdf",
        status="ANALYZED",
        document_type="INVOICE",
        extracted_data={"document_type": "INVOICE", "workflow_routing": {"route": "INVOICE_RECONCILIATION"}},
    )
    foreign = DocumentAnalysis(
        tenant_id=user_b.tenant_id,
        uploaded_by=user_b.id,
        filename="invoice-b.pdf",
        mime_type="application/pdf",
        status="ANALYZED",
        document_type="INVOICE",
        extracted_data={"document_type": "INVOICE", "workflow_routing": {"route": "INVOICE_RECONCILIATION"}},
    )
    db.session.add_all([own, foreign])
    db.session.commit()

    response = logged_in_client_a.get("/api/document-intelligence?limit=100")
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert [row["id"] for row in payload["analyses"]] == [own.id]
    assert payload["analyses"][0]["filename"] == "invoice-a.pdf"
    assert payload["analyses"][0]["extracted_data"]["workflow_routing"]["route"] == "INVOICE_RECONCILIATION"
    assert "storage_path" not in payload["analyses"][0]
    assert payload["limit"] == 100
