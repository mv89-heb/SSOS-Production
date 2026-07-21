import io
import os

from app.services.ocr_service import OCRService, validate_upload, OCRProviderError, NullOCRProvider


def test_validate_upload_accepts_known_image_type():
    validate_upload("invoice.png", "image/png", file_size=1000, max_size=5_000_000)  # no exception


def test_validate_upload_rejects_bad_extension():
    try:
        validate_upload("invoice.exe", "image/png", file_size=1000, max_size=5_000_000)
        assert False, "expected OCRProviderError"
    except OCRProviderError:
        pass


def test_validate_upload_rejects_mismatched_mime_type():
    try:
        validate_upload("invoice.png", "application/x-msdownload", file_size=1000, max_size=5_000_000)
        assert False, "expected OCRProviderError"
    except OCRProviderError:
        pass


def test_validate_upload_rejects_oversized_file():
    try:
        validate_upload("invoice.png", "image/png", file_size=10_000_000, max_size=5_000_000)
        assert False, "expected OCRProviderError"
    except OCRProviderError:
        pass


def test_process_document_missing_file_returns_error():
    service = OCRService(provider=NullOCRProvider())
    result = service.process_document("/tmp/does-not-exist-ssos.png")
    assert result["status"] == "error"


def test_process_document_with_null_provider_succeeds(tmp_path):
    file_path = tmp_path / "sample.png"
    file_path.write_bytes(b"not a real image, just bytes for existence check")

    service = OCRService(provider=NullOCRProvider())
    result = service.process_document(str(file_path))
    assert result["status"] == "success"
    assert result["text"] == ""
    assert result["detected_items"] == []


def test_ocr_upload_endpoint_end_to_end(logged_in_client_a, make_order):
    create, _, _ = make_order(logged_in_client_a)
    order_id = create.get_json()["order"]["id"]

    # A minimal valid PNG header is enough to pass extension/MIME validation;
    # OCR extraction itself gracefully no-ops without a tesseract binary installed.
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    data = {"file": (io.BytesIO(png_bytes), "invoice.png")}
    resp = logged_in_client_a.post(f"/api/orders/{order_id}/ocr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["result"]["status"] == "success"


def test_ocr_upload_requires_existing_order(logged_in_client_a):
    data = {"file": (io.BytesIO(b"x"), "invoice.png")}
    resp = logged_in_client_a.post("/api/orders/999999/ocr", data=data, content_type="multipart/form-data")
    assert resp.status_code == 404
