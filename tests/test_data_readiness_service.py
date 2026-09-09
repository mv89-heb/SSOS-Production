def test_data_readiness_endpoint_reports_empty_tenant_without_fabrication(logged_in_client_a):
    response = logged_in_client_a.get("/api/price-intelligence/data-readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["products"]["active"] == 0
    assert payload["supplier_offers"]["active"] == 0
    assert payload["price_intelligence"]["history_rows"] == 0
    assert payload["price_intelligence"]["observation_rows"] == 0
    assert payload["orders"]["with_realized_value"] == 0
    assert payload["readiness"] == {
        "catalog": False,
        "supplier_comparison": False,
        "historical_prices": False,
        "realized_spend": False,
        "stock_risk": False,
    }
