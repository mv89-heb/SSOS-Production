
from decimal import Decimal

import pytest

from app.services.vat_service import normalize_price_before_vat


def test_normalize_price_before_vat_keeps_net_values():
    assert normalize_price_before_vat(Decimal("100"), "before_vat") == Decimal("100.00")


def test_normalize_price_before_vat_removes_default_vat_from_gross_values():
    assert normalize_price_before_vat(Decimal("118"), "after_vat") == Decimal("100.00")


def test_normalize_price_before_vat_supports_historical_vat_rate():
    assert normalize_price_before_vat(Decimal("117"), "after_vat", Decimal("0.17")) == Decimal("100.00")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1"])
def test_normalize_price_before_vat_rejects_invalid_amounts(value):
    with pytest.raises(ValueError):
        normalize_price_before_vat(value, "after_vat")
