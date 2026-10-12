from app.services.master_product_matching_service import MasterProductMatchingService


def test_normalization_handles_hebrew_and_measure_aliases():
    normalize = MasterProductMatchingService.normalize
    assert normalize("  חלב טרי תנובה 3 אחוז ליטר  ") == "חלב טרי תנובה 3% l"
    assert normalize("Milk, TNUVA 1L!") == "milk tnuva 1 l"


def test_fuzzy_match_rejects_different_package_sizes():
    score, reason = MasterProductMatchingService._score(
        "חלב תנובה 3% 1 ליטר",
        "חלב תנובה 3% 2 ליטר",
    )
    assert score == 0
    assert reason == "PACKAGE_SIZE_MISMATCH"


def test_fuzzy_match_rejects_different_product_variants():
    score, reason = MasterProductMatchingService._score(
        "חלב תנובה 3% 1 ליטר",
        "חלב תנובה 1.5% 1 ליטר",
    )
    assert score == 0
    assert reason == "PRODUCT_VARIANT_MISMATCH"


def test_semantically_similar_hebrew_name_scores_as_candidate():
    score, reason = MasterProductMatchingService._score(
        "חלב תנובה 3 אחוז 1 ליטר",
        "חלב טרי תנובה 3% 1L",
    )
    assert score >= 0.62
    assert reason == "FUZZY_TEXT"


def test_intake_requires_valid_supplier_and_positive_price(logged_in_client_a):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק בדיקה"}).get_json()["supplier"]
    bad = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier["id"], "supplier_name": "חלב תנובה 3%", "price": 0,
    })
    assert bad.status_code == 400


def test_intake_creates_pending_product_and_manual_approval_creates_master(logged_in_client_a):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק בדיקה"}).get_json()["supplier"]
    intake = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier["id"], "supplier_name": "חלב תנובה 3% 1 ליטר",
        "supplier_sku": "MILK-001", "price": 7.5, "unit": "ליטר",
    })
    assert intake.status_code == 201, intake.get_json()
    item = intake.get_json()["supplier_product"]
    assert item["match_status"] == "PENDING"
    assert item["master_product_id"] is None

    approved = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{item['id']}/approve",
        json={"create_master_product": {"canonical_name": "חלב תנובה 3% 1 ליטר", "brand": "תנובה", "base_unit": "ליטר"}},
    )
    assert approved.status_code == 200, approved.get_json()
    assert approved.get_json()["supplier_product"]["match_status"] == "APPROVED"
    assert approved.get_json()["master_product"]["canonical_name"] == "חלב תנובה 3% 1 ליטר"


def test_exact_barcode_links_to_existing_master_but_fuzzy_match_waits_for_approval(logged_in_client_a):
    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק א"}).get_json()["supplier"]
    first = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_a["id"], "supplier_name": "חלב תנובה 3% 1 ליטר",
        "supplier_sku": "A-1", "barcode": "7290000000012", "price": 7.5,
    }).get_json()["supplier_product"]
    created = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{first['id']}/approve",
        json={"create_master_product": {"canonical_name": "חלב תנובה 3% 1 ליטר", "barcode": "7290000000012"}},
    )
    assert created.status_code == 200

    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק ב"}).get_json()["supplier"]
    exact = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_b["id"], "supplier_name": "חלב טרי תנובה 3 אחוז 1L",
        "supplier_sku": "B-1", "barcode": "7290000000012", "price": 7.2,
    }).get_json()["supplier_product"]
    assert exact["match_status"] == "APPROVED"
    assert exact["master_product_id"] == created.get_json()["master_product"]["id"]


def test_pending_products_are_tenant_scoped(logged_in_client_a, logged_in_client_b):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק א"}).get_json()["supplier"]
    created = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier["id"], "supplier_name": "מוצר בדיקה", "supplier_sku": "P-1", "price": 5,
    })
    assert created.status_code == 201
    response = logged_in_client_b.get("/api/catalog/supplier-products/pending")
    assert response.status_code == 200
    assert response.get_json()["supplier_products"] == []
