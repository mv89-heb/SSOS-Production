from types import SimpleNamespace

from app.services.price_intelligence_service import PriceIntelligenceService


def _service(product, offers, suppliers):
    service = object.__new__(PriceIntelligenceService)
    service.tenant_id = 1
    service.product_repo = SimpleNamespace(get_by_id_or_404=lambda _product_id: product)
    service.supplier_repo = SimpleNamespace(get_by_id=lambda supplier_id: suppliers.get(supplier_id))
    service.offer_repo = SimpleNamespace(get_by_product=lambda _product_id: offers)
    return service


def test_comparison_keeps_currency_mismatch_visible():
    product = SimpleNamespace(
        id=10,
        supplier_id=1,
        current_price=100,
        currency="ILS",
        unit="יחידה",
        units_per_carton=None,
        supplier=None,
        supplier_offers=[],
        to_dict=lambda: {"id": 10},
    )
    offer = SimpleNamespace(
        active=True,
        price=20,
        supplier_id=2,
        unit="יחידה",
        units_per_carton=None,
        currency="USD",
    )
    suppliers = {
        1: SimpleNamespace(name="ספק ראשי"),
        2: SimpleNamespace(name="ספק חלופי"),
    }

    result = _service(product, [offer], suppliers).compare_product(10)

    assert [row["supplier_id"] for row in result["offers"]] == [1]
    assert len(result["incomparable_offers"]) == 1
    assert result["incomparable_offers"][0]["supplier_id"] == 2
    assert "מטבע שונה" in result["incomparable_offers"][0]["incomparable_reason"]


def test_comparison_normalizes_compatible_units_and_ranks_offers():
    product = SimpleNamespace(
        id=10,
        supplier_id=1,
        current_price=120,
        currency="ILS",
        unit="קרטון",
        units_per_carton=12,
        supplier=None,
        supplier_offers=[],
        to_dict=lambda: {"id": 10},
    )
    offer = SimpleNamespace(
        active=True,
        price=11,
        supplier_id=2,
        unit="יחידה",
        units_per_carton=None,
        currency="ILS",
    )
    suppliers = {
        1: SimpleNamespace(name="ספק ראשי"),
        2: SimpleNamespace(name="ספק חלופי"),
    }

    result = _service(product, [offer], suppliers).compare_product(10)

    assert [row["supplier_id"] for row in result["offers"]] == [1, 2]
    assert result["best_offer"]["supplier_id"] == 1
    assert result["saving_per_unit"] == 0.0


def test_incomparable_reason_for_unit_mismatch():
    left = {"currency": "ILS", "comparison_unit": "KG"}
    right = {"currency": "ILS", "comparison_unit": "L"}

    assert "יחידת השוואה שונה" in PriceIntelligenceService._incomparable_reason(left, right)
