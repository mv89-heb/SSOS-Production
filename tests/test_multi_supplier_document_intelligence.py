from types import SimpleNamespace

from app.services.gemini_provider import GeminiProvider
from app.services.product_matching_service import ProductMatchingService
from app.services.document_intelligence_service import DocumentIntelligenceService


def test_merge_page_results_keeps_multiple_suppliers_on_same_and_different_pages():
    pages = [
        {"document_type": "INVOICE", "supplier_sections": [
            {"supplier": {"name": "ספק א", "customer_number": "100"}, "items": [{"description": "מוצר א"}]},
            {"supplier": {"name": "ספק ב", "customer_number": "200"}, "items": [{"description": "מוצר ב"}]},
        ]},
        {"supplier_sections": [
            {"supplier": {"name": "ספק א", "customer_number": "100"}, "items": [{"description": "מוצר ג"}]},
            {"supplier": {"name": "ספק ג", "customer_number": "300"}, "items": [{"description": "מוצר ד"}]},
        ]},
    ]
    merged = GeminiProvider._merge_page_results(pages, 2)
    assert merged["pages_processed"] == 2
    assert len(merged["supplier_sections"]) == 3
    by_number = {section["supplier"]["customer_number"]: section for section in merged["supplier_sections"]}
    assert by_number["100"]["page_numbers"] == [1, 2]
    assert [item["page_number"] for item in by_number["100"]["items"]] == [1, 2]
    assert by_number["200"]["page_numbers"] == [1]
    assert by_number["300"]["page_numbers"] == [2]
    assert len(merged["items"]) == 4


def test_product_matching_is_supplier_aware_per_section():
    supplier_a = SimpleNamespace(id=1, name="ספק א", customer_number="100")
    supplier_b = SimpleNamespace(id=2, name="ספק ב", customer_number="200")
    product_a = SimpleNamespace(id=11, name="חלב 3%", description="חלב 3%", barcode="", supplier_sku="A-1", sku="MILK-A", unit="יח", units_per_carton=None, supplier_id=1, supplier=supplier_a)
    product_b = SimpleNamespace(id=22, name="חלב 3%", description="חלב 3%", barcode="", supplier_sku="B-1", sku="MILK-B", unit="יח", units_per_carton=None, supplier_id=2, supplier=supplier_b)
    service = ProductMatchingService(tenant_id=1)
    service._suppliers = [supplier_a, supplier_b]
    service._products = [product_a, product_b]
    enriched = service.enrich_document({"supplier_sections": [
        {"supplier": {"name": "ספק א", "customer_number": "100"}, "items": [{"description": "חלב 3%", "supplier_sku": "A-1", "unit_price": 7}]},
        {"supplier": {"name": "ספק ב", "customer_number": "200"}, "items": [{"description": "חלב 3%", "supplier_sku": "B-1", "unit_price": 8}]},
    ]})
    assert enriched["supplier_count"] == 2
    assert enriched["supplier_matching"][0]["supplier_id"] == 1
    assert enriched["supplier_matching"][1]["supplier_id"] == 2
    assert enriched["supplier_sections"][0]["items"][0]["supplier_matching"]["supplier_id"] == 1
    assert enriched["supplier_sections"][1]["items"][0]["supplier_matching"]["supplier_id"] == 2
    assert enriched["supplier_sections"][0]["items"][0]["product_matching"]["best_match"]["product_id"] == 11
    assert enriched["supplier_sections"][1]["items"][0]["product_matching"]["best_match"]["product_id"] == 22


def test_ambiguous_supplier_name_is_not_auto_assigned():
    supplier_a = SimpleNamespace(id=1, name="ספק ישראל", customer_number="")
    supplier_b = SimpleNamespace(id=2, name="ספק ישראלי", customer_number="")
    service = ProductMatchingService(tenant_id=1)
    service._suppliers = [supplier_a, supplier_b]
    service._products = []
    match = service.match_supplier({"name": "ספק ישראל"})
    assert match["decision"] == "REVIEW"
    assert match["supplier_id"] is None


def test_single_supplier_legacy_shape_remains_supported():
    supplier = SimpleNamespace(id=1, name="ספק א", customer_number="100")
    product = SimpleNamespace(id=11, name="מוצר א", description="מוצר א", barcode="", supplier_sku="A-1", sku="A", unit="יח", units_per_carton=None, supplier_id=1, supplier=supplier)
    service = ProductMatchingService(tenant_id=1)
    service._suppliers = [supplier]
    service._products = [product]
    enriched = service.enrich_document({"supplier": {"name": "ספק א", "customer_number": "100"}, "items": [{"description": "מוצר א", "supplier_sku": "A-1"}]})
    assert enriched["supplier_count"] == 1
    assert enriched["supplier"]["name"] == "ספק א"
    assert enriched["items"][0]["product_matching"]["best_match"]["product_id"] == 11


def test_stream_parser_exposes_complete_product_rows_before_json_finishes():
    partial = (
        '{"supplier_sections":[{"supplier":{"name":"ספק א"},"items":['
        '{"description":"חלב 3%","quantity":2,"unit_price":7.5},'
        '{"description":"לחם","quantity":1,"unit_price":4},'
        '{"description":"שורה שעדיין נכתבת'
    )
    items = GeminiProvider._extract_completed_json_items(partial)
    assert [item["description"] for item in items] == ["חלב 3%", "לחם"]



def test_document_reference_text_is_not_matched_as_a_product_or_counted_as_a_line():
    service = ProductMatchingService(tenant_id=1)
    service._suppliers = []
    service._products = []
    service._supplier_offers = []
    data = service.enrich_document({
        "document_type": "INVOICE",
        "document_number": "INV-901",
        "supplier": {"name": "מאפיית קויליטש בע״מ"},
        "items": [
            {
                "description": "תעודת משלוח מספר 90190 מיום 15/10/2026",
                "quantity": 1,
                "page_number": 1,
            },
            {
                "description": "חלה גדולה",
                "quantity": 174,
                "unit_price": 8,
                "page_number": 1,
            },
        ],
    })

    reference, product = data["items"]
    assert reference["line_type"] == "DOCUMENT_REFERENCE"
    assert reference["product_matching"] == {
        "decision": "NO_MATCH",
        "best_match": None,
        "suggestions": [],
    }
    assert product["line_type"] == "PRODUCT_LINE"
    routing = DocumentIntelligenceService.build_workflow_routing(data)
    assert routing["item_count"] == 1
    assert routing["status"] == "READY_FOR_REVIEW"



def test_hebrew_document_reference_detection_handles_unicode_word_boundaries():
    references = [
        "תעודת משלוח מספר 90190 מיום 15/10/2026",
        "חשבונית מס 12345",
        "מספר מסמך: 77",
        "מסמך מספר 88",
    ]
    for description in references:
        assert ProductMatchingService.is_document_reference_line(description)

    assert not ProductMatchingService.is_document_reference_line("חלה גדולה")
    assert not ProductMatchingService.is_document_reference_line("תעודת משלוחים מיוחדת")
