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
    extracted = {"description": "חלב תנובה 3 אחוז 1 ליטר", "unit": "ליטר"}
    without_supplier, _ = service._candidate_score(
        extracted,
        product(name="חלב תנובה טרי", description="מוצר חלב", supplier_id=20, barcode=""),
    )
    with_supplier, _ = service._candidate_score(
        extracted,
        product(name="חלב תנובה טרי", description="מוצר חלב", supplier_id=10, barcode=""),
        supplier_id=10,
    )
    assert with_supplier > without_supplier


def test_unrelated_product_is_below_match_threshold():
    service = ProductMatchingService(1)
    extracted = {"description": "מפתח ברגים תעשייתי"}
    score, method = service._candidate_score(extracted, product())
    assert score < 0.45
    assert method == "NAME_SIMILARITY"


def test_supplier_name_core_matches_legal_and_location_suffixes():
    service = ProductMatchingService(1)
    service._suppliers = [
        SimpleNamespace(id=10, name="גידרון", customer_number=None),
        SimpleNamespace(id=50, name="אריאל שיווק בשר", customer_number=None),
    ]
    service._products = []
    result = service.match_supplier({"name": 'גידרון תעשיות בע"מ - שוהם קפוא'})
    assert result["supplier_id"] == 10
    assert result["confidence"] == 1.0
    assert result["method"] == "NAME_CORE"
    assert result["decision"] == "AUTO_MATCH"


def test_supplier_context_prevents_cross_supplier_product_match():
    service = ProductMatchingService(1)
    service._suppliers = []
    service._products = [
        product(id=1877, name="ביגל רומני", supplier_id=42, supplier=SimpleNamespace(id=42, name="חלת הבית"), barcode="", supplier_sku=None),
        product(id=1774, name="בייגל רומני אפוי קפוא", supplier_id=10, supplier=SimpleNamespace(id=10, name="גידרון"), barcode="", supplier_sku=None),
    ]
    result = service.match_line({"description": "בייגל רומני"}, supplier_id=10)
    assert result["best_match"]["product_id"] == 1774
    assert result["best_match"]["supplier_id"] == 10


def test_product_description_ignores_common_invoice_wording():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": 'קוקיס+ שוקולד לבן חלבי'},
        product(name="קוקיס שוקולד לבן", barcode="", supplier_sku=None),
        supplier_id=10,
    )
    assert score >= 0.98
    assert method == "NAME_SIMILARITY"
