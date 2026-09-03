from io import BytesIO
from types import SimpleNamespace

from app.models.document_analysis import DocumentAnalysis


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
        def generate_structured_from_file(path, schema, system_instruction=None):
            assert path
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

    db.session.expire_all()
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row.storage_path is None
    assert not __import__("os").path.exists(temp_path)
