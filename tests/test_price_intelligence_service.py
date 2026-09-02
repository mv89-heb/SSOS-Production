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
    assert unit == "CARTON"


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
