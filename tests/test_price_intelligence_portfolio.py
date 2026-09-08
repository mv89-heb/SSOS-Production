from types import SimpleNamespace

from app.services.price_intelligence_service import PriceIntelligenceService


def _summary_service(comparisons):
    service = object.__new__(PriceIntelligenceService)
    service.tenant_id = 1
    products = [SimpleNamespace(id=product_id, name=f"Product {product_id}", sku=f"SKU-{product_id}") for product_id in comparisons]
    service.product_repo = SimpleNamespace(get_all_for_matching=lambda: products)
    service.history_repo = SimpleNamespace(list_all=lambda limit=10: [])
    service.compare_product = lambda product_id: comparisons[product_id]
    return service


def _comparison(current_price, best_price=None, supplier_id=1, best_supplier_id=2):
    current = {"supplier_id": supplier_id, "supplier_name": "Current", "normalized_price": current_price, "currency": "ILS"}
    offers = []
    best = None
    if best_price is not None:
        best = {"supplier_id": best_supplier_id, "supplier_name": "Alternative", "normalized_price": best_price, "currency": "ILS"}
        offers = [best]
    return {"current": current, "best_offer": best, "offers": offers, "incomparable_offers": []}


def test_portfolio_summary_calculates_only_real_price_opportunities():
    service = _summary_service({1: _comparison(100, 80), 2: _comparison(50, 60), 3: _comparison(20)})

    result = service.get_portfolio_summary()

    assert result["products_analyzed"] == 3
    assert result["products_with_comparable_alternatives"] == 2
    assert result["opportunity_products"] == 1
    assert result["potential_savings"] == 20.0
    assert result["potential_savings_percent"] == 11.7647
    assert result["top_opportunities"][0]["product_id"] == 1
    assert result["top_opportunities"][0]["best_supplier"] == "Alternative"


def test_supplier_scores_rank_by_coverage_and_price_wins():
    service = _summary_service({
        1: _comparison(100, 80, supplier_id=1, best_supplier_id=2),
        2: _comparison(90, 70, supplier_id=1, best_supplier_id=2),
        3: _comparison(80, 70, supplier_id=2, best_supplier_id=1),
    })

    result = service.get_supplier_price_scores()
    by_id = {row["supplier_id"]: row for row in result["suppliers"]}

    assert result["products_analyzed"] == 3
    assert by_id[2]["wins"] == 2
    assert by_id[1]["wins"] == 1
    assert by_id[2]["score"] > by_id[1]["score"]
