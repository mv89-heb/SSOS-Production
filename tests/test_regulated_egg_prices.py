def _add_egg_product(client, name, sku):
    supplier_response = client.post("/api/catalog/suppliers", json={"name": f"Egg Supplier {sku}"})
    assert supplier_response.status_code == 201, supplier_response.get_json()
    supplier_id = supplier_response.get_json()["supplier"]["id"]
    response = client.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": name, "sku": sku, "current_price": 12.5, "currency": "ILS",
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["product"]["id"]


def test_regulated_egg_price_history_is_seeded_and_does_not_touch_catalog(logged_in_client_a):
    product_id = _add_egg_product(logged_in_client_a, "ביצים L 12 יחידות", "EGG-L-12")
    _add_egg_product(logged_in_client_a, "ביצי חופש L 12 יחידות", "EGG-FREE-L")
    response = logged_in_client_a.get("/api/regulatory-prices/eggs")
    assert response.status_code == 200
    payload = response.get_json()
    current = {row["size_code"]: row["max_consumer_price"] for row in payload["current_release"]}
    assert current == {"M": None, "L": None, "XL": None}
    assert all(row["change_percent"] == 2.1 for row in payload["current_release"])
    assert all(row["verification_status"] == "ANNOUNCED_RATE_ONLY" for row in payload["current_release"])
    matches = {row["product_name"]: row for row in payload["matched_products"]}
    assert matches["ביצים L 12 יחידות"]["regulated"] is True
    assert matches["ביצים L 12 יחידות"]["max_consumer_price"] == 14.54
    assert matches["ביצי חופש L 12 יחידות"]["regulated"] is False
    assert matches["ביצי חופש L 12 יחידות"]["max_consumer_price"] is None
    catalog = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    product = next(item for item in catalog if item["id"] == product_id)
    assert product["current_price"] == 12.5


def test_regulated_egg_price_release_requires_official_source_and_is_idempotent(logged_in_client_a):
    payload = {
        "effective_date": "2027-05-01",
        "published_at": "2027-04-20",
        "source_url": "https://www.gov.il/he/example",
        "source_title": "הודעת עדכון רשמית",
        "verified_official": True,
        "change_percent": 1.5,
        "items": [
            {"size_code": "M", "max_consumer_price": 13.60},
            {"size_code": "L", "max_consumer_price": 14.75},
            {"size_code": "XL", "max_consumer_price": 16.05},
        ],
    }
    response = logged_in_client_a.post("/api/regulatory-prices/eggs/releases", json=payload)
    assert response.status_code == 201, response.get_json()
    assert len(response.get_json()["release"]) == 3
    duplicate = logged_in_client_a.post("/api/regulatory-prices/eggs/releases", json=payload)
    assert duplicate.status_code == 409
    invalid = dict(payload, effective_date="2027-06-01", source_url="https://example.com/egg-prices")
    rejected = logged_in_client_a.post("/api/regulatory-prices/eggs/releases", json=invalid)
    assert rejected.status_code == 400



def test_official_announcement_parser_only_matches_egg_price_updates():
    from scripts.check_regulated_egg_prices import find_latest_egg_announcement

    html = """
    <html><body>
      <a href="/he/news/egg-price-update">22/10/26 הודעות לעיתונות מחירי הביצים שבפיקוח יתעדכנו בכ-2.1%</a>
      <a href="/he/news/other">הודעה אחרת על חקלאות</a>
    </body></html>
    """
    result = find_latest_egg_announcement(html)
    assert result is not None
    assert result["url"] == "https://www.gov.il/he/news/egg-price-update"
    assert "2.1%" in result["title"]
    assert result["published_at"] == "22/10/26"
    assert find_latest_egg_announcement("<html><a href='/news/other'>עדכון אחר</a></html>") is None
