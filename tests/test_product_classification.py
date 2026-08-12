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
    assert product["category_reviewed"] is False


def test_user_feedback_is_reused_for_same_normalized_name(logged_in_client_a, app, db):
    supplier_response = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Frozen Supplier"})
    supplier_id = supplier_response.get_json()["supplier"]["id"]
    product_response = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier_id, "name": "טבעות בצל קפואות 1 קג", "current_price": 12},
    )
    product_id = product_response.get_json()["product"]["id"]

    response = logged_in_client_a.post(
        f"/api/catalog/products/{product_id}/category-feedback",
        json={"category": "קפואים"},
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["product"]["category_source"] == "USER"
    assert response.get_json()["product"]["category_reviewed"] is True

    with app.app_context():
        product = db.session.get(Product, product_id)
        result = ProductClassificationService().classify(product.tenant_id, product.name)

    assert result["category"] == "קפואים"
    assert result["source"] == "LEARNED"


def test_classification_feedback_is_tenant_scoped(logged_in_client_a, logged_in_client_b, app, db):
    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Tenant A Supplier"}).get_json()["supplier"]["id"]
    product_a = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier_a, "name": "אורז בסמטי", "current_price": 10},
    ).get_json()["product"]["id"]

    response = logged_in_client_a.post(
        f"/api/catalog/products/{product_a}/category-feedback",
        json={"category": "משקאות"},
    )
    assert response.status_code == 200

    cross_tenant = logged_in_client_b.post(
        f"/api/catalog/products/{product_a}/category-feedback",
        json={"category": "פירות"},
    )
    assert cross_tenant.status_code == 404

    with app.app_context():
        product = db.session.get(Product, product_a)
        result = ProductClassificationService().classify(product.tenant_id, product.name)
        assert result["category"] == "משקאות"
