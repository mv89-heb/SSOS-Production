from decimal import Decimal
from types import SimpleNamespace

from app.services.gemini_price_completion_service import GeminiPriceCompletionService


def test_price_completion_schema_and_prompt():
    service = GeminiPriceCompletionService(1, 2, {"GEMINI_API_KEY": "test", "GEMINI_MODEL": "gemini-3.5-flash-lite"})
    product = SimpleNamespace(id=7, name="אורז בסמטי 5 ק"ג", description="מותג בדיקה", barcode="7290000000000",
                              sku="RICE-5", supplier_sku="SUP-RICE-5", unit="קרטון", units_per_carton=4, category="מזון")
    prompt = service._prompt(product)
    assert "7290000000000" in prompt
    assert "Google Search grounding" in prompt
    assert service._schema()["properties"]["price_ils"]["type"] == "NUMBER"


def test_positive_decimal_parser():
    assert GeminiPriceCompletionService._number("12.50") == Decimal("12.50")
    assert GeminiPriceCompletionService._number("0") is None
