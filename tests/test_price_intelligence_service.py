import pytest

from app.services.price_intelligence_service import PriceIntelligenceService


def test_normalize_units():
    assert PriceIntelligenceService.normalize_unit("יחידה") == "UNIT"
    assert PriceIntelligenceService.normalize_unit("ק\"ג") == "KG"
    assert PriceIntelligenceService.normalize_unit("liter") == "L"


def test_carton_price_is_normalized_to_unit_price():
    price, unit = PriceIntelligenceService.normalize_offer_price(120, "קרטון", 12)
    assert price == 10
    assert unit == "UNIT"


def test_carton_without_quantity_is_not_falsely_normalized():
    price, unit = PriceIntelligenceService.normalize_offer_price(120, "קרטון", None)
    assert price == 120
    # Unknown pack quantity means there is no safe comparable unit.
    assert unit is None


def test_mass_and_volume_are_normalized_to_purchase_units():
    price, unit = PriceIntelligenceService.normalize_offer_price(0.5, "גרם")
    assert price == 500
    assert unit == "KG"

    price, unit = PriceIntelligenceService.normalize_offer_price(0.01, "ml")
    assert price == 10
    assert unit == "L"


def test_invalid_decimal_values_raise_instead_of_silently_becoming_zero():
    with pytest.raises(ValueError, match="Invalid decimal value"):
        PriceIntelligenceService._decimal("not-a-number")


def test_blank_unit_is_none():
    assert PriceIntelligenceService.normalize_unit("  ") is None


def test_portfolio_counts_only_real_alternative_suppliers():
    from types import SimpleNamespace

    service = PriceIntelligenceService.__new__(PriceIntelligenceService)
    service.product_repo = SimpleNamespace(get_all_for_matching=lambda: [SimpleNamespace(id=1)])
    service.history_repo = SimpleNamespace(list_all=lambda limit: [])
    current = {"supplier_id": 10, "supplier_name": "Current", "normalized_price": 10, "currency": "ILS", "primary": True}
    service.compare_product = lambda product_id: {
        "current": current,
        "best_offer": current,
        "offers": [current],
    }

    summary = service.get_portfolio_summary()

    assert summary["products_with_comparable_alternatives"] == 0
    assert summary["opportunity_products"] == 0
    assert summary["potential_savings"] == 0


def test_supplier_scores_do_not_double_count_the_current_supplier():
    from types import SimpleNamespace

    service = PriceIntelligenceService.__new__(PriceIntelligenceService)
    service.product_repo = SimpleNamespace(get_all_for_matching=lambda: [SimpleNamespace(id=1)])
    current = {"supplier_id": 10, "supplier_name": "Current", "normalized_price": 10, "currency": "ILS", "primary": True}
    alternative = {"supplier_id": 20, "supplier_name": "Alternative", "normalized_price": 8, "currency": "ILS", "primary": False}
    service.compare_product = lambda product_id: {
        "current": current,
        "best_offer": alternative,
        "offers": [current, alternative],
    }

    result = service.get_supplier_price_scores()
    suppliers = {row["supplier_id"]: row for row in result["suppliers"]}

    assert result["products_analyzed"] == 1
    assert suppliers[10]["participation"] == 1
    assert suppliers[20]["participation"] == 1
    assert suppliers[10]["coverage_percent"] <= 100
    assert suppliers[20]["coverage_percent"] <= 100
