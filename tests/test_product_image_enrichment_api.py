from unittest.mock import patch

from app.models.product import Product


def _make_product(client, supplier_name, product_name, sku, barcode, image_url=None):
    supplier = client.post("/api/catalog/suppliers", json={"name": supplier_name})
    assert supplier.status_code == 201, supplier.get_json()
    response = client.post("/api/catalog/products", json={
        "supplier_id": supplier.get_json()["supplier"]["id"],
        "name": product_name, "sku": sku, "barcode": barcode,
        "current_price": 12, "image_url": image_url,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["product"]["id"]


def test_image_enrichment_fills_missing_image_and_records_source(logged_in_client_a, db):
    product_id = _make_product(logged_in_client_a, "Image Supplier", "Milk 1L", "IMG-1", "1234567890123")
    candidate = {
        "image_url": "https://images.openfoodfacts.org/images/products/123/456/789/0123/front_en.1.400.jpg",
        "reason": "matched", "source": "Open Food Facts",
        "source_url": "https://world.openfoodfacts.org/product/1234567890123",
    }
    with patch("app.routes.catalog.lookup_product_image", return_value=candidate) as lookup:
        response = logged_in_client_a.post("/api/catalog/products/images/enrich", json={"limit": 10})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["matched"] == 1
    lookup.assert_called_once_with("1234567890123", "Milk 1L")
    product = db.session.get(Product, product_id)
    assert product.image_url == candidate["image_url"]
    assert product.image_source == "Open Food Facts"
    assert product.image_source_url == candidate["source_url"]
    assert product.image_checked_at is not None


def test_image_enrichment_never_overwrites_existing_custom_image(logged_in_client_a, db):
    product_id = _make_product(
        logged_in_client_a, "Custom Image Supplier", "Custom product", "IMG-CUSTOM",
        "1234567890124", "https://example.com/custom-image.jpg",
    )
    with patch("app.routes.catalog.lookup_product_image") as lookup:
        response = logged_in_client_a.post("/api/catalog/products/images/enrich", json={"limit": 10})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["attempted"] == 0
    lookup.assert_not_called()
    from app.extensions import db
    product = db.session.get(Product, product_id)
    assert product.image_url == "https://example.com/custom-image.jpg"


def test_image_enrichment_rejects_invalid_batch_size(logged_in_client_a):
    response = logged_in_client_a.post("/api/catalog/products/images/enrich", json={"limit": 101})
    assert response.status_code == 400
