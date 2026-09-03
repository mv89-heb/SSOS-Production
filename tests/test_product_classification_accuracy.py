from app.services.product_classification_service import (
    ProductClassificationService,
    _phrase_present,
    normalize_product_name,
)


def _classifier_without_db():
    service = ProductClassificationService()
    service._latest_feedback = lambda tenant_id, normalized_name: None
    service._similar_feedback = lambda tenant_id, normalized_name: (None, 0.0)
    return service


def test_normalization_removes_quantity_without_losing_product_words():
    assert normalize_product_name('תפוח אדמה 2 ק"ג') == 'תפוח אדמה'


def test_phrase_matching_uses_word_boundaries():
    assert _phrase_present('תפוח אדמה', 'תפוח אדמה')
    assert not _phrase_present('תפוח אדמה', 'תפוח')


def test_common_ambiguous_products_use_hard_rules():
    service = _classifier_without_db()
    cases = {
        'תפוח אדמה': 'ירקות',
        'תפוחי אדמה 5 ק"ג': 'ירקות',
        'פלפל שחור טחון': 'רטבים ותבלינים',
        'טונה בקופסה 160 גרם': 'שימורים',
        'שניצל עוף קפוא': 'קפואים',
        'צלחות חד פעמיות': 'חד פעמי',
        'שניצל עוף': 'עוף',
    }
    for name, expected in cases.items():
        result = service.classify(1, name)
        assert result['category'] == expected, (name, result)
        assert result['confidence'] >= 0.99


def test_unknown_product_abstains():
    service = _classifier_without_db()
    result = service.classify(1, 'מוצר מיוחד ללא זיהוי')
    assert result['category'] is None
    assert result['source'] == 'RULES'
