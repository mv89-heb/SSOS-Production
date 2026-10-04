from decimal import Decimal
from types import SimpleNamespace

from app.services.gemini_price_completion_service import GeminiPriceCompletionService


def test_price_completion_schema_and_prompt():
    service = GeminiPriceCompletionService(1, 2, {"GEMINI_API_KEY": "test", "GEMINI_MODEL": "gemini-3.5-flash-lite"})
    product = SimpleNamespace(id=7, name='אורז בסמטי 5 ק"ג', description="מותג בדיקה", barcode="7290000000000",
                              sku="RICE-5", supplier_sku="SUP-RICE-5", unit="קרטון", units_per_carton=4, category="מזון",
                              supplier=SimpleNamespace(name="ספק ראשי"))
    prompt = service._prompt(product)
    assert "7290000000000" in prompt
    assert "Google Search grounding" in prompt
    assert service._schema()["properties"]["price_ils"]["type"] == "NUMBER"


def test_positive_decimal_parser():
    assert GeminiPriceCompletionService._number("12.50") == Decimal("12.50")
    assert GeminiPriceCompletionService._number("0") is None


def test_price_completion_rejects_price_from_unverified_supplier(monkeypatch):
    service = GeminiPriceCompletionService(1, 2, {"GEMINI_API_KEY": "test"})
    product = SimpleNamespace(id=8, name="מוצר בדיקה", current_price=0, supplier=SimpleNamespace(name="ספק ראשי"))
    monkeypatch.setattr(service, "find_price", lambda _product: {
        "found": True,
        "price_ils": 19.90,
        "price_unit": "יחידה",
        "package_description": "יחידה",
        "matched_product": "מוצר בדיקה",
        "match_type": "WEB_SEARCH",
        "matched_supplier": "ספק אחר",
        "supplier_match": False,
        "confidence": 95,
        "source_urls": ["https://example.test/product"],
        "evidence": "מחיר של ספק אחר",
    })
    result = service.complete_product(product)
    assert result["status"] == "unresolved"
    assert product.current_price == 0
    assert "הספק הראשי" in result["reason"]
