from app.services.ai_service import AIResult


class FakeAI:
    def is_available(self):
        return True

    def generate_text(self, prompt, *, system_instruction=None):
        assert "DETERMINISTIC SAVINGS" in prompt
        assert "PRICE HISTORY" in prompt
        return AIResult(
            success=True,
            text='{"recommendation":"Supplier B","confidence":91,"reasons":["מחיר נמוך יותר"],"risks":["יש לבדוק תנאי התקשרות"],"trend":"יציב","actions":["בדוק את ההצעה לפני הזמנה"]}',
            provider="gemini",
            model="gemini-test",
        )


def test_gemini_insight_uses_deterministic_comparison(logged_in_client_a, monkeypatch):
    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier A"}).get_json()["supplier"]["id"]
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier B"}).get_json()["supplier"]["id"]
    product = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_a,
        "name": "Rice",
        "sku": "RICE-AI-1",
        "current_price": 12,
        "currency": "ILS",
        "unit": "unit",
    }).get_json()["product"]
    offer = logged_in_client_a.post("/api/catalog/products/%s/offers" % product["id"], json={
        "supplier_id": supplier_b,
        "price": 9,
        "currency": "ILS",
        "unit": "unit",
    })
    assert offer.status_code in (200, 201), offer.get_json()

    import app.routes.price_intelligence as route_module
    monkeypatch.setattr(route_module.AIService, "from_config", lambda config: FakeAI())

    response = logged_in_client_a.post(
        f"/api/price-intelligence/products/{product['id']}/ai-insight",
        json={"quantity": 100},
    )

    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["success"] is True
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-test"
    assert body["insight"]["recommendation"] == "Supplier B"
    assert body["insight"]["confidence"] == 91


def test_gemini_insight_is_unavailable_without_provider(logged_in_client_a, monkeypatch):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier"}).get_json()["supplier"]["id"]
    product = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier,
        "name": "Milk",
        "sku": "MILK-AI-1",
        "current_price": 8,
    }).get_json()["product"]

    import app.routes.price_intelligence as route_module

    class Unavailable:
        def is_available(self):
            return False

    monkeypatch.setattr(route_module.AIService, "from_config", lambda config: Unavailable())

    response = logged_in_client_a.post(
        f"/api/price-intelligence/products/{product['id']}/ai-insight",
        json={"quantity": 10},
    )
    assert response.status_code == 503
    assert response.get_json()["success"] is False
