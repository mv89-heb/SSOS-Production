def test_master_catalog_lists_one_canonical_product_and_compares_all_suppliers(logged_in_client_a):
    from app.extensions import db
    from app.models.master_product import MasterProduct

    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק א"}).get_json()["supplier"]
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק ב"}).get_json()["supplier"]

    first = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_a["id"], "supplier_name": "בורקס גבינה 1 ק״ג",
        "supplier_sku": "BOREK-A", "price": 42, "unit": "יחידה",
    })
    assert first.status_code == 201, first.get_json()
    item_a = first.get_json()["supplier_product"]
    created = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{item_a['id']}/approve",
        json={"create_master_product": {"canonical_name": "בורקס גבינה 1 ק״ג", "base_unit": "יחידה"}},
    )
    assert created.status_code == 200, created.get_json()
    master_id = created.get_json()["master_product"]["id"]

    second = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_b["id"], "supplier_name": "בורקס גבינה 1 ק״ג",
        "supplier_sku": "BOREK-B", "price": 37, "unit": "יחידה",
    })
    assert second.status_code == 201, second.get_json()
    item_b = second.get_json()["supplier_product"]
    approved = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{item_b['id']}/approve",
        json={"master_product_id": master_id},
    )
    assert approved.status_code == 200, approved.get_json()

    catalog = logged_in_client_a.get("/api/catalog/master-products")
    assert catalog.status_code == 200, catalog.get_json()
    matching = [p for p in catalog.get_json()["master_products"] if p["id"] == master_id]
    assert len(matching) == 1
    assert matching[0]["supplier_count"] == 2
    assert matching[0]["current_price"] == 37.0

    comparison = logged_in_client_a.get(f"/api/catalog/master-products/{master_id}/comparison")
    assert comparison.status_code == 200, comparison.get_json()
    group = comparison.get_json()["groups"][0]
    assert len(group["offers"]) == 2
    assert group["best_offer"]["supplier_id"] == supplier_b["id"]


def test_master_catalog_and_comparison_are_tenant_scoped(logged_in_client_a, logged_in_client_b):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק פרטי"}).get_json()["supplier"]
    intake = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier["id"], "supplier_name": "מוצר סודי", "supplier_sku": "SECRET-1",
        "price": 5, "unit": "יחידה",
    })
    item = intake.get_json()["supplier_product"]
    created = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{item['id']}/approve",
        json={"create_master_product": {"canonical_name": "מוצר סודי", "base_unit": "יחידה"}},
    )
    master_id = created.get_json()["master_product"]["id"]

    catalog_b = logged_in_client_b.get("/api/master-products")
    assert catalog_b.status_code == 200
    assert all(item["id"] != master_id for item in catalog_b.get_json()["master_products"])
    comparison_b = logged_in_client_b.get(f"/api/master-products/{master_id}/comparison")
    assert comparison_b.status_code == 404



def test_recent_invoice_observation_updates_master_product_supplier_comparison(logged_in_client_a, db):
    from datetime import datetime, timedelta
    from app.models.price_observation import PriceObservation
    from app.models.product import Product

    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק א"}).get_json()["supplier"]
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "ספק ב"}).get_json()["supplier"]
    legacy_product_response = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_a["id"], "name": "חלב תנובה 1 ליטר",
        "sku": "MILK-LEGACY-OBS", "current_price": 10, "unit": "יחידה",
    })
    assert legacy_product_response.status_code == 201, legacy_product_response.get_json()
    legacy_product_id = legacy_product_response.get_json()["product"]["id"]

    first = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_a["id"], "supplier_name": "חלב תנובה 1 ליטר",
        "supplier_sku": "MILK-A", "price": 10, "unit": "יחידה",
    }).get_json()["supplier_product"]
    created = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{first['id']}/approve",
        json={"create_master_product": {"canonical_name": "חלב תנובה 1 ליטר", "base_unit": "יחידה"}},
    ).get_json()
    master_id = created["master_product"]["id"]

    second = logged_in_client_a.post("/api/catalog/supplier-products/intake", json={
        "supplier_id": supplier_b["id"], "supplier_name": "חלב תנובה 1 ליטר",
        "supplier_sku": "MILK-B", "price": 12, "unit": "יחידה",
    }).get_json()["supplier_product"]
    approved = logged_in_client_a.post(
        f"/api/catalog/supplier-products/{second['id']}/approve",
        json={"master_product_id": master_id},
    )
    assert approved.status_code == 200, approved.get_json()

    legacy_product = db.session.get(Product, legacy_product_id)
    db.session.add(PriceObservation(
        tenant_id=legacy_product.tenant_id,
        product_id=legacy_product.id,
        supplier_id=supplier_b["id"],
        observed_price=8,
        currency="ILS",
        unit="יחידה",
        source_type="INVOICE",
        source_document_id=321,
        match_confidence=0.99,
        observed_at=datetime.utcnow() + timedelta(days=1),
    ))
    db.session.commit()

    response = logged_in_client_a.get(f"/api/master-products/{master_id}/comparison")
    assert response.status_code == 200, response.get_json()
    group = response.get_json()["groups"][0]
    best = group["best_offer"]
    assert best["supplier_id"] == supplier_b["id"]
    assert best["price"] == 8
    assert best["source_type"] == "INVOICE"
    assert best["source_document_id"] == 321
