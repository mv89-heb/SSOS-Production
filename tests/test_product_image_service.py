import json
from unittest.mock import patch

from app.services.product_image_service import lookup_product_image


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_lookup_uses_exact_barcode_and_accepts_off_image_url():
    payload = {"status": 1, "product": {
        "code": "0123456789012", "product_name": "Milk",
        "image_front_url": "https://images.openfoodfacts.org/images/products/012/345/678/9012/front_en.1.400.jpg",
    }}
    with patch("app.services.product_image_service.urlopen", return_value=FakeResponse(payload)):
        result = lookup_product_image("0123456789012")
    assert result["reason"] == "matched"
    assert result["source"] == "Open Food Facts"
    assert result["image_url"].startswith("https://images.openfoodfacts.org/")


def test_lookup_rejects_barcode_mismatch():
    payload = {"status": 1, "product": {"code": "9999999999999", "image_front_url": "https://images.openfoodfacts.org/a.jpg"}}
    with patch("app.services.product_image_service.urlopen", return_value=FakeResponse(payload)):
        result = lookup_product_image("0123456789012")
    assert result["reason"] == "barcode_mismatch"
    assert result["image_url"] is None


def test_lookup_rejects_untrusted_image_hosts():
    payload = {"status": 1, "product": {"code": "0123456789012", "image_front_url": "https://example.com/product.jpg"}}
    with patch("app.services.product_image_service.urlopen", return_value=FakeResponse(payload)):
        result = lookup_product_image("0123456789012")
    assert result["reason"] == "image_not_available"


def test_lookup_skips_synthetic_barcodes_without_network_call():
    with patch("app.services.product_image_service.urlopen") as mocked:
        result = lookup_product_image("990000010000123")
    assert result["reason"] == "missing_or_synthetic_barcode"
    mocked.assert_not_called()



def test_name_lookup_requires_exact_normalized_name():
    payload = {"products": [{
        "code": "1234567890123", "product_name": "חלב תנובה 3% 1 ליטר",
        "image_front_url": "https://images.openfoodfacts.org/images/products/123/456/789/0123/front_he.1.400.jpg",
    }]}
    with patch("app.services.product_image_service._request_json", return_value=payload):
        result = lookup_product_image("990000010000123", "תנובה חלב 3% 1 ליטר")
    assert result["reason"] == "matched_by_exact_name"
    assert result["match_method"] == "exact_normalized_name"


def test_name_lookup_rejects_near_match():
    payload = {"products": [{
        "code": "1234567890123", "product_name": "חלב תנובה 1 ליטר",
        "image_front_url": "https://images.openfoodfacts.org/images/products/123/456/789/0123/front_he.1.400.jpg",
    }]}
    with patch("app.services.product_image_service._request_json", return_value=payload):
        result = lookup_product_image("990000010000123", "תנובה חלב 3% 1 ליטר")
    assert result["image_url"] is None
    assert result["reason"] == "product_not_found"
