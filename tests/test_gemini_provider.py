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
