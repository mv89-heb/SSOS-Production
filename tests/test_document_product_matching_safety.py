from types import SimpleNamespace

from app.services.product_matching_service import ProductMatchingService


def product(name: str):
    return SimpleNamespace(
        id=1,
        name=name,
        description=None,
        barcode=None,
        supplier_sku=None,
        sku=None,
        unit=None,
        units_per_carton=None,
        supplier_id=1,
        supplier=None,
    )


def test_small_dishes_never_match_large_plates_automatically():
    extracted = {"description": "לפתניות צבעוני 25 יח' קרם"}
    catalog_product = product("צלחות גדול צבעוני 25 יח קרם")

    assert ProductMatchingService._variant_conflict(extracted, catalog_product) is True
    score, method = ProductMatchingService._candidate_score(extracted, catalog_product, supplier_id=1)
    assert score == 0
    assert method == "PRODUCT_VARIANT_MISMATCH"


def test_missing_soup_variant_keeps_similar_plate_for_manual_review():
    extracted = {"description": 'צלחות מרק =Classic= קרם 100 יח\' למיקרוגל כשל"פ עד"ח אחת'}
    catalog_product = product('צלחות גדול =Classic= קרם 100 יח למיקרוגל כשל"פ עד"ח אחת')

    score, method = ProductMatchingService._candidate_score(extracted, catalog_product, supplier_id=1)

    assert score < 0.93
    assert method == "NAME_SIMILARITY"
