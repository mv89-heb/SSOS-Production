from types import SimpleNamespace

from app.services.gemini_provider import GeminiProvider
from app.services.product_matching_service import ProductMatchingService


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
