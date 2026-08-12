from app.models.product import Product
from app.services.product_classification_service import ProductClassificationService


def test_product_is_classified_automatically_on_create(logged_in_client_a):
    response = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Dairy Supplier"})
    supplier_id = response.get_json()["supplier"]["id"]

    response = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier_id, "name": "חלב 3% תנובה", "current_price": 8.5},
    )

    assert response.status_code == 201, response.get_json()
    product = response.get_json()["product"]
    assert product["category"] == "מוצרי חלב"
    assert product["category_source"] in {"RULES", "LEARNED"}
    assert product["category_confidence"] is not None


def test_user_feedback_is_reused_for_same_normalized_name(app, db):
    with app.app_context():
        service = ProductClassificationService()
        feedback = service.record_feedback(
            tenant_id=1,
            user_id=None,
            product_id=1,
            product_name="טבעות בצל קפואות 1 קג",
            actual_category="קפואים",
            predicted_category="ירקות",
            confidence=0.55,
        )
        db.session.commit()
        result = service.classify(1, "טבעות בצל קפואות 1 קג")

        assert feedback.actual_category == "קפואים"
        assert result["category"] == "קפואים"
        assert result["source"] == "LEARNED"
