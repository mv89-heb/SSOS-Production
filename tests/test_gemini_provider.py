from app.services.gemini_provider import GeminiProvider


def test_merge_page_results_preserves_all_items_and_page_numbers():
    result = GeminiProvider._merge_page_results(
        [
            {
                "document_type": "INVOICE",
                "supplier": {"name": "Supplier A"},
                "items": [{"description": "Milk", "unit_price": 5.5}],
            },
            {
                "supplier": {"customer_number": "123"},
                "items": [
                    {"description": "Cheese", "unit_price": 12.0},
                    {"description": "Bread", "unit_price": 7.0},
                ],
            },
        ],
        page_count=2,
    )

    assert result["page_count"] == 2
    assert result["pages_processed"] == 2
    assert result["extraction_mode"] == "pdf_page_by_page"
    assert [item["page_number"] for item in result["items"]] == [1, 2, 2]
    assert [item["description"] for item in result["items"]] == ["Milk", "Cheese", "Bread"]
    assert result["supplier"] == {"name": "Supplier A", "customer_number": "123"}


def test_merge_page_results_handles_pages_without_items():
    result = GeminiProvider._merge_page_results(
        [{"items": []}, {"items": [{"description": "Item"}]}],
        page_count=2,
    )

    assert result["pages_processed"] == 2
    assert result["items"] == [{"description": "Item", "page_number": 2}]


def test_retryable_error_detection():
    assert GeminiProvider._is_retryable_error(TimeoutError("read operation timed out"))
    assert GeminiProvider._is_retryable_error(RuntimeError("503 UNAVAILABLE"))
    assert GeminiProvider._is_retryable_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not GeminiProvider._is_retryable_error(ValueError("400 invalid argument"))


def test_pdf_uses_single_whole_document_request(tmp_path):
    from pypdf import PdfWriter
    from unittest.mock import Mock

    pdf_path = tmp_path / "document.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with pdf_path.open("wb") as handle:
        writer.write(handle)

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-3.6-flash"
    provider.fallback_model = None
    provider._client = Mock()
    provider._client.models.generate_content.return_value.text = '{"items": [], "supplier_sections": []}'

    result = provider.generate_structured_from_file(
        str(pdf_path),
        {"type": "object", "properties": {"items": {"type": "array"}}},
    )

    assert result.success is True
    assert result.data["page_count"] == 2
    assert result.data["pages_processed"] == 2
    assert result.data["extraction_mode"] == "pdf_whole_document"
    assert provider._client.models.generate_content.call_count == 1


def test_provider_defaults_to_flash_lite():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-3.5-flash-lite"
    provider.fallback_model = "gemini-3.6-flash"
    provider.thinking_level = "low"
    assert provider.model == "gemini-3.5-flash-lite"
    assert provider.fallback_model == "gemini-3.6-flash"
