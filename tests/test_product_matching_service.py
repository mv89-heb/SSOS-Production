from types import SimpleNamespace

from app.services.product_matching_service import ProductMatchingService


def product(**kwargs):
    defaults = {
        "id": 1,
        "name": "חלב תנובה 3% 1 ליטר",
        "description": "חלב טרי",
        "barcode": "7290000000012",
        "sku": "MILK-3-1L",
        "supplier_sku": "TN-100",
        "unit": "ליטר",
        "units_per_carton": None,
        "supplier_id": 10,
        "supplier": SimpleNamespace(id=10, name="תנובה"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_normalize_handles_hebrew_unicode_and_punctuation():
    assert ProductMatchingService.normalize("  חלב\u05f4 תנובה 3%  ") == 'חלב" תנובה 3'
    assert ProductMatchingService.compact("729-000-000-012") == "729000000012"


def test_barcode_is_exact_high_confidence_match():
    service = ProductMatchingService(1)
    extracted = {"description": "מוצר אחר", "barcode": "7290000000012"}
    score, method = service._candidate_score(extracted, product())
    assert score == 1.0
    assert method == "BARCODE"


def test_supplier_sku_matches_before_name_similarity():
    service = ProductMatchingService(1)
    extracted = {"description": "שם שונה לגמרי", "supplier_sku": "TN-100"}
    score, method = service._candidate_score(extracted, product())
    assert score == 0.99
    assert method == "SUPPLIER_SKU"


def test_similar_hebrew_product_name_is_high_confidence_enough_for_review():
    service = ProductMatchingService(1)
    extracted = {"description": "חלב תנובה 3 אחוז 1 ליטר", "unit": "ליטר"}
    score, method = service._candidate_score(extracted, product())
    assert score >= 0.75
    assert method == "NAME_SIMILARITY"


def test_supplier_context_boosts_same_supplier():
    service = ProductMatchingService(1)
    extracted = {"description": "חלב תנובה 3% 1 ליטר"}
    without_supplier, _ = service._candidate_score(extracted, product(supplier_id=20))
    with_supplier, _ = service._candidate_score(extracted, product(supplier_id=10), supplier_id=10)
    assert with_supplier > without_supplier


def test_unrelated_product_is_below_match_threshold():
    service = ProductMatchingService(1)
    extracted = {"description": "מפתח ברגים תעשייתי"}
    score, method = service._candidate_score(extracted, product())
    assert score < 0.45
    assert method == "NAME_SIMILARITY"
