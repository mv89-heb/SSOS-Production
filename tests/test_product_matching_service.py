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


def test_low_confidence_candidate_is_suggestion_not_selected_match():
    service = ProductMatchingService(1)
    service._suppliers = []
    service._products = [
        product(id=99, name="שנק קינמון", description="מאפה", supplier_id=10, supplier=SimpleNamespace(id=10, name="גידרון"), barcode="", supplier_sku=None),
    ]
    result = service.match_line({"description": "מישטח קרטון"}, supplier_id=10)
    assert result["decision"] == "LOW_CONFIDENCE"
    assert result["best_match"] is None
    assert result["suggestions"]
    assert result["suggestions"][0]["product_id"] == 99


def test_synthetic_barcode_never_becomes_authoritative_match():
    service = ProductMatchingService(1)
    extracted = {"description": "מוצר אחר", "barcode": "990000010000123"}
    score, method = service._candidate_score(
        extracted,
        product(barcode="990000010000123", supplier_sku=None),
    )
    assert method == "NAME_SIMILARITY"
    assert score < 1.0



def test_explicit_small_vs_large_variant_is_rejected_even_with_similar_name():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "צלחות קטן Classic קרם"},
        product(name="צלחות גדול Classic קרם", description="", barcode="", supplier_sku=None),
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_explicit_soup_plate_stays_in_review_against_regular_plate():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "צלחות מרק Classic קרם"},
        product(name="צלחות גדול Classic קרם", description="", barcode="", supplier_sku=None),
    )
    assert 0 < score < 0.93
    assert method == "NAME_SIMILARITY"


def test_cutlery_types_are_never_interchangeable():
    service = ProductMatchingService(1)
    cases = [
        ("כפות קרם ארוז 50 יח", "סכין קרם ארוז 50 יח"),
        ("מזלג קרם ארוז 50 יח", "סכין קרם ארוז 50 יח"),
        ("מפיות לבנות 100 יח", "כפות קרם ארוז 50 יח"),
    ]
    for source, catalog_name in cases:
        score, method = service._candidate_score(
            {"description": source},
            product(name=catalog_name, description="", barcode="", supplier_sku=None),
        )
        assert score == 0, (source, catalog_name, score, method)
        assert method == "PRODUCT_VARIANT_MISMATCH"


def test_exact_barcode_does_not_override_explicit_variant_conflict():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "צלחות קטן קרם", "barcode": "7290000000012"},
        product(name="צלחות גדול קרם", description="", barcode="7290000000012"),
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_same_explicit_variant_can_still_use_exact_identity():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "צלחות קטן קרם", "barcode": "7290000000012"},
        product(name="צלחות קטן קרם", description="", barcode="7290000000012"),
    )
    assert score == 1.0
    assert method == "BARCODE"



def test_explicit_package_volume_and_fat_percentage_conflicts_are_rejected():
    service = ProductMatchingService(1)
    cases = [
        ("חלב תנובה 3% 1 ליטר", "חלב תנובה 3% 2 ליטר"),
        ("חלב תנובה 3% 1 ליטר", "חלב תנובה 1.5% 1 ליטר"),
    ]
    for source, catalog_name in cases:
        score, method = service._candidate_score(
            {"description": source},
            product(name=catalog_name, description="", barcode="", supplier_sku=None),
        )
        assert score == 0, (source, catalog_name, score, method)
        assert method == "PRODUCT_VARIANT_MISMATCH"


def test_explicit_pack_count_conflict_is_rejected():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "כפות קרם ארוז 50 יח"},
        product(name="כפות קרם ארוז 100 יח", description="", barcode="", supplier_sku=None),
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_candidate_missing_explicit_variant_cannot_be_auto_selected():
    service = ProductMatchingService(1)
    service._suppliers = []
    service._products = [
        product(
            id=101,
            name="צלחות קרם Classic",
            description="",
            barcode="",
            supplier_sku=None,
        ),
    ]
    result = service.match_line({"description": "צלחות קטן קרם Classic"})
    assert result["decision"] == "REVIEW"
    assert result["best_match"]["product_id"] == 101


def test_small_dishes_do_not_match_large_plates_automatically():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "לפתניות צבעוני 25 יח' קרם"},
        product(name="צלחות גדול צבעוני 25 יח קרם", description="", barcode="", supplier_sku=None),
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_soup_bowls_are_not_equivalent_to_regular_plates():
    service = ProductMatchingService(1)
    score, method = service._candidate_score(
        {"description": "מרקיות צבעוני 25 יח' קרם"},
        product(name="צלחות גדול צבעוני 25 יח קרם", description="", barcode="", supplier_sku=None),
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"

def test_supplier_offer_sku_is_exact_identity_but_keeps_variant_guard():
    service = ProductMatchingService(1)
    offer = SimpleNamespace(supplier_sku="48090/2")
    score, method = service._candidate_score(
        {"description": "אשפתון 80/90 שחור 400 יח", "supplier_sku": "48090/2"},
        product(name="אשפתון 80/90 שחור 400 יח", barcode="", supplier_sku=None),
        supplier_id=10,
        supplier_offer=offer,
    )
    assert score == 0.99
    assert method == "SUPPLIER_OFFER_SKU"

    score, method = service._candidate_score(
        {"description": "צלחות קטן קרם", "supplier_sku": "48090/2"},
        product(name="צלחות גדול קרם", barcode="", supplier_sku=None),
        supplier_id=10,
        supplier_offer=offer,
    )
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_match_line_includes_products_available_from_supplier_as_alternate_offer():
    service = ProductMatchingService(1)
    service._suppliers = []
    service._products = [
        product(
            id=1678,
            name="אשפתון רול אנד באג 50*70",
            description="",
            barcode="",
            supplier_sku=None,
            supplier_id=20,
            supplier=SimpleNamespace(id=20, name="ספק ראשי אחר"),
        ),
    ]
    service._supplier_offers = [
        SimpleNamespace(
            product_id=1678,
            supplier_id=10,
            supplier_sku=None,
            active=True,
            supplier=SimpleNamespace(id=10, name="ר. שמאי"),
        ),
    ]

    result = service.match_line(
        {"description": "אשפתון רול אנד באג 50*70"},
        supplier_id=10,
    )

    assert result["best_match"]["product_id"] == 1678
    assert result["best_match"]["supplier_id"] == 10
    assert result["best_match"]["supplier_name"] == "ר. שמאי"
    assert result["best_match"]["decision"] == "AUTO_MATCH"



def test_single_supplier_section_inherits_document_level_supplier_when_section_is_empty():
    service = ProductMatchingService(1)
    data = {
        "supplier": {"name": "גידרון תעשיות בע\"מ", "customer_number": "12345"},
        "supplier_sections": [{"supplier": {"name": "", "customer_number": ""}, "items": [{"description": "שניצל קפוא"}]}],
    }

    sections = service._build_supplier_sections(data)

    assert len(sections) == 1
    assert sections[0]["supplier"]["name"] == "גידרון תעשיות בע\"מ"
    assert sections[0]["supplier"]["customer_number"] == "12345"


def test_supplier_section_identity_is_not_overwritten_by_document_level_supplier():
    service = ProductMatchingService(1)
    data = {
        "supplier": {"name": "ספק כללי"},
        "supplier_sections": [{"supplier": {"name": "ר. שמאי"}, "items": []}],
    }

    sections = service._build_supplier_sections(data)

    assert sections[0]["supplier"]["name"] == "ר. שמאי"
