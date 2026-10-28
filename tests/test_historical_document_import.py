from decimal import Decimal

from app.routes.historical_document_import import _date, _decimal, _norm, _supplier_from_extraction


def test_historical_import_date_and_decimal_parsing_preserve_unknown_values():
    assert _date("2024-05-17") is not None
    assert _date("not-a-date") is None
    assert _date(None) is None
    assert _decimal("125.40") == Decimal("125.40")
    assert _decimal(None) is None
    assert _decimal("not-a-price") is None


def test_historical_import_supplier_matching_does_not_invent_supplier():
    name, supplier_id, multi_supplier = _supplier_from_extraction({
        "supplier": {"name": "ספק לדוגמה"},
        "supplier_matching": {"supplier_id": 17, "decision": "AUTO_MATCH"},
        "supplier_sections": [{"supplier": {"name": "ספק לדוגמה"}, "supplier_matching": {"supplier_id": 17, "decision": "AUTO_MATCH"}}],
    })
    assert name == "ספק לדוגמה"
    assert supplier_id == 17
    assert multi_supplier is False

    name, supplier_id, multi_supplier = _supplier_from_extraction({
        "supplier": {},
        "supplier_sections": [
            {"supplier": {"name": "ספק א"}},
            {"supplier": {"name": "ספק ב"}},
        ],
    })
    assert name is None
    assert supplier_id is None
    assert multi_supplier is True


def test_historical_import_supplier_normalization_is_deterministic():
    assert _norm("  ספק   א בע״מ ") == "ספק א בע״מ"
