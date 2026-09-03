from io import BytesIO
from types import SimpleNamespace


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
