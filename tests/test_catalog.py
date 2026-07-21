def test_tenant_catalog_isolation(logged_in_client_a, logged_in_client_b):
    # Tenant A creates a supplier
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Tenant A Supplier"})

    # Tenant B should see an empty list
    resp = logged_in_client_b.get("/api/catalog/suppliers")
    assert resp.status_code == 200
    assert len(resp.get_json()["suppliers"]) == 0


def test_list_products_active_only_filter(logged_in_client_a):
    s_resp = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Filter Test Supplier"})
    s_id = s_resp.get_json()["supplier"]["id"]

    active = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Active Product", "sku": "ACT1", "current_price": 10.0,
    })
    inactive_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Inactive Product", "sku": "INA1", "current_price": 10.0, "active": False,
    }).get_json()["product"]["id"]

    all_products = logged_in_client_a.get(f"/api/catalog/products?supplier_id={s_id}")
    assert len(all_products.get_json()["products"]) == 2

    active_only = logged_in_client_a.get(f"/api/catalog/products?supplier_id={s_id}&active=true")
    names = [p["name"] for p in active_only.get_json()["products"]]
    assert "Active Product" in names
    assert "Inactive Product" not in names
    assert inactive_id not in [p["id"] for p in active_only.get_json()["products"]]
    assert active.status_code == 201


def test_get_single_product(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Widget", "sku": "W1", "current_price": 5.0,
    }).get_json()["product"]["id"]

    resp = logged_in_client_a.get(f"/api/catalog/products/{p_id}")
    assert resp.status_code == 200
    assert resp.get_json()["product"]["name"] == "Widget"


def test_get_nonexistent_product_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/catalog/products/999999")
    assert resp.status_code == 404


def test_get_single_supplier(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Detail Supplier"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.get(f"/api/catalog/suppliers/{s_id}")
    assert resp.status_code == 200
    assert resp.get_json()["supplier"]["name"] == "Detail Supplier"


def test_get_nonexistent_supplier_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/catalog/suppliers/999999")
    assert resp.status_code == 404


def test_update_supplier(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Old Name"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.put(f"/api/catalog/suppliers/{s_id}", json={"name": "New Name", "phone": "12345"})
    assert resp.status_code == 200
    supplier = resp.get_json()["supplier"]
    assert supplier["name"] == "New Name"
    assert supplier["phone"] == "12345"


def test_soft_delete_supplier_via_active_flag(logged_in_client_a):
    """Suppliers/products use active=False as the 'soft delete' — the row
    stays, so any order that already referenced them keeps working."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Deactivate Me"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.put(f"/api/catalog/suppliers/{s_id}", json={"active": False})
    assert resp.status_code == 200
    assert resp.get_json()["supplier"]["active"] is False

    active_only = logged_in_client_a.get("/api/catalog/suppliers?active=true")
    ids = [s["id"] for s in active_only.get_json()["suppliers"]]
    assert s_id not in ids

    all_suppliers = logged_in_client_a.get("/api/catalog/suppliers")
    ids_all = [s["id"] for s in all_suppliers.get_json()["suppliers"]]
    assert s_id in ids_all


def test_employee_cannot_update_supplier(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    s_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.put(f"/api/catalog/suppliers/{s_id}", json={"name": "Hijacked"})
    assert resp.status_code == 403


def test_me_includes_tenant_info(logged_in_client_a):
    resp = logged_in_client_a.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tenant"]["name"] == "Acme Co"
    assert body["tenant"]["id"] == body["user"]["tenant_id"]


def test_audit_log_includes_user_email(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Audit Email Test"})
    resp = logged_in_client_a.get("/api/audit")
    logs = resp.get_json()["logs"]
    matching = [log for log in logs if log["action"] == "catalog.supplier_created"]
    assert matching
    assert matching[0]["user_email"] == "admin@acme.test"


def test_order_snapshot_integrity(logged_in_client_a):
    # 1. Setup Supplier and Product
    s_resp = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Snapshot Test Supplier"})
    s_id = s_resp.get_json()["supplier"]["id"]

    p_resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Test Product", "sku": "SKU001", "current_price": 100.0
    })
    p_id = p_resp.get_json()["product"]["id"]

    # 2. Create Order (line items copied from the catalog at this moment)
    o_resp = logged_in_client_a.post("/api/orders", json={
        "supplier_id": s_id,
        "items": [{"product_id": p_id, "quantity": 5}]
    })
    order = o_resp.get_json()["order"]
    assert order["final_total"] == 500.0
    assert order["items"][0]["unit_price"] == 100.0

    # 3. Change Product Price in Catalog
    price_change = logged_in_client_a.put(f"/api/catalog/products/{p_id}", json={"current_price": 250.0})
    assert price_change.status_code == 200

    # 4. Fetch Order again - price must remain 100.0
    fetch_resp = logged_in_client_a.get(f"/api/orders/{order['id']}")
    fetched_order = fetch_resp.get_json()["order"]
    assert fetched_order["items"][0]["unit_price"] == 100.0
    assert fetched_order["final_total"] == 500.0


def test_snapshot_survives_product_deletion(logged_in_client_a):
    """Deleting a product from the catalog must not affect orders already
    placed against it — they hold a copy, not a foreign key."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Doomed Product", "sku": "D1", "current_price": 20.0,
    }).get_json()["product"]["id"]

    o_resp = logged_in_client_a.post("/api/orders", json={
        "supplier_id": s_id, "items": [{"product_id": p_id, "quantity": 3}],
    })
    order_id = o_resp.get_json()["order"]["id"]

    deleted = logged_in_client_a.delete(f"/api/catalog/products/{p_id}")
    assert deleted.status_code == 200
    assert logged_in_client_a.get(f"/api/catalog/products/{p_id}").status_code == 404

    fetched_order = logged_in_client_a.get(f"/api/orders/{order_id}").get_json()["order"]
    assert fetched_order["items"][0]["product_name"] == "Doomed Product"
    assert fetched_order["items"][0]["unit_price"] == 20.0
    assert fetched_order["final_total"] == 60.0


def test_employee_cannot_update_product(client_a, tenant_a_admin):
    from test_security import _register_employee  # noqa: local import to reuse the helper

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    s_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "P", "sku": "P1", "current_price": 1.0,
    }).get_json()["product"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.put(f"/api/catalog/products/{p_id}", json={"current_price": 999.0})
    assert resp.status_code == 403


def test_audit_log_for_catalog_actions(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Audit Test"})
    resp = logged_in_client_a.get("/api/audit")
    logs = resp.get_json()["logs"]
    actions = [log["action"] for log in logs]
    assert "catalog.supplier_created" in actions


# --- Phase 1: Product Model Upgrade (image/barcode/category/unit/stock) ----

def test_create_product_with_phase1_fields(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Cola 1.5L", "sku": "COLA-15", "current_price": 6.5,
        "image_url": "https://example.com/cola.png",
        "barcode": "7290000000012",
        "category": "משקאות",
        "unit": "ארגז",
        "units_per_carton": 6,
        "supplier_sku": "SUP-COLA-15",
        "current_stock": 40,
        "min_stock": 10,
        "recommended_stock": 60,
    })
    assert resp.status_code == 201
    product = resp.get_json()["product"]
    assert product["image_url"] == "https://example.com/cola.png"
    assert product["barcode"] == "7290000000012"
    assert product["category"] == "משקאות"
    assert product["unit"] == "ארגז"
    assert product["units_per_carton"] == 6
    assert product["supplier_sku"] == "SUP-COLA-15"
    assert product["current_stock"] == 40
    assert product["min_stock"] == 10
    assert product["recommended_stock"] == 60


def test_create_product_without_phase1_fields_still_works(logged_in_client_a):
    """Backward compatibility: none of the new fields are required."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Plain Product", "sku": "PLAIN1", "current_price": 1.0,
    })
    assert resp.status_code == 201
    product = resp.get_json()["product"]
    assert product["image_url"] is None
    assert product["barcode"] is None
    assert product["category"] is None
    assert product["current_stock"] is None


def test_update_product_phase1_fields(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    p_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Widget", "sku": "W1", "current_price": 5.0,
    }).get_json()["product"]["id"]

    resp = logged_in_client_a.put(f"/api/catalog/products/{p_id}", json={
        "category": "חד פעמי", "current_stock": 5, "min_stock": 20,
    })
    assert resp.status_code == 200
    product = resp.get_json()["product"]
    assert product["category"] == "חד פעמי"
    assert product["current_stock"] == 5
    assert product["min_stock"] == 20


def test_create_product_rejects_negative_stock(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Bad Product", "sku": "BAD1", "current_price": 1.0,
        "current_stock": -5,
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_product_data"


def test_create_product_rejects_non_numeric_barcode(logged_in_client_a):
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Bad Barcode Product", "sku": "BB1", "current_price": 1.0,
        "barcode": "not-a-barcode!",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_product_data"


def test_create_product_rejects_unknown_field_instead_of_crashing(logged_in_client_a):
    """Previously create_product passed **data straight into the model
    constructor — an unrecognized key raised a raw TypeError (500) instead
    of being silently ignored like update_product already did. Now both
    funnel through the same whitelist, so an unknown field is just dropped
    and the request still succeeds."""
    s_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Weird Product", "sku": "WEIRD1", "current_price": 1.0,
        "totally_unknown_field": "should be ignored, not crash",
    })
    assert resp.status_code == 201


# --- Phase 2: Supplier Catalog Engine (alternate-supplier price offers) ---

def _make_product(client, supplier_name="Primary Supplier", price=10.0):
    s_id = client.post("/api/catalog/suppliers", json={"name": supplier_name}).get_json()["supplier"]["id"]
    p_id = client.post("/api/catalog/products", json={
        "supplier_id": s_id, "name": "Comparison Product", "current_price": price,
    }).get_json()["product"]["id"]
    return s_id, p_id


def test_create_and_list_offers(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt Supplier"}).get_json()["supplier"]["id"]

    resp = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 8.5, "unit": "קילו", "units_per_carton": 12,
    })
    assert resp.status_code == 201
    offer = resp.get_json()["offer"]
    assert offer["supplier_id"] == alt_id
    assert offer["supplier_name"] == "Alt Supplier"
    assert offer["price"] == 8.5

    listed = logged_in_client_a.get(f"/api/catalog/products/{p_id}/offers")
    assert listed.status_code == 200
    offers = listed.get_json()["offers"]
    assert len(offers) == 1
    assert offers[0]["price"] == 8.5


def test_offers_sorted_cheapest_first(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "B"}).get_json()["supplier"]["id"]
    supplier_c = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "C"}).get_json()["supplier"]["id"]

    logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": supplier_b, "price": 12.0})
    logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": supplier_c, "price": 6.0})

    offers = logged_in_client_a.get(f"/api/catalog/products/{p_id}/offers").get_json()["offers"]
    assert [o["price"] for o in offers] == [6.0, 12.0]


def test_cannot_offer_same_supplier_twice_for_same_product(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]

    first = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 5.0})
    assert first.status_code == 201
    dup = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 4.0})
    assert dup.status_code == 409


def test_cannot_offer_products_own_primary_supplier(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    resp = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": primary_id, "price": 5.0})
    assert resp.status_code == 400


def test_offer_rejects_negative_price(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    resp = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": -1.0})
    assert resp.status_code == 400


def test_update_offer(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    offer_id = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 5.0,
    }).get_json()["offer"]["id"]

    resp = logged_in_client_a.put(f"/api/catalog/products/{p_id}/offers/{offer_id}", json={"price": 4.25})
    assert resp.status_code == 200
    assert resp.get_json()["offer"]["price"] == 4.25


def test_delete_offer(logged_in_client_a):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    offer_id = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 5.0,
    }).get_json()["offer"]["id"]

    resp = logged_in_client_a.delete(f"/api/catalog/products/{p_id}/offers/{offer_id}")
    assert resp.status_code == 200
    assert logged_in_client_a.get(f"/api/catalog/products/{p_id}/offers").get_json()["offers"] == []


def test_offers_require_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    primary_id, p_id = _make_product(client_a)
    alt_id = client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 5.0})
    assert resp.status_code == 403


def test_offers_are_tenant_isolated(logged_in_client_a, logged_in_client_b):
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 5.0})

    resp = logged_in_client_b.get(f"/api/catalog/products/{p_id}/offers")
    assert resp.status_code == 404


def test_deleting_alternate_supplier_removes_its_offers(logged_in_client_a, app, db):
    """Cascade: deleting a supplier that only appears as an alternate-offer
    source must not orphan supplier_product_offers rows."""
    from app.models.supplier_offer import SupplierProductOffer

    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 5.0})

    with app.app_context():
        from app.models.supplier import Supplier
        supplier = db.session.get(Supplier, alt_id)
        db.session.delete(supplier)
        db.session.commit()
        assert db.session.query(SupplierProductOffer).filter_by(supplier_id=alt_id).count() == 0


def test_offer_creation_rejects_cross_tenant_supplier_id(logged_in_client_a, logged_in_client_b):
    """Tenant A must not be able to create an offer on its own product that
    references Tenant B's supplier_id."""
    primary_id, p_id = _make_product(logged_in_client_a)
    foreign_supplier_id = logged_in_client_b.post(
        "/api/catalog/suppliers", json={"name": "Tenant B Supplier"}
    ).get_json()["supplier"]["id"]

    resp = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": foreign_supplier_id, "price": 5.0,
    })
    assert resp.status_code == 404


def test_offer_update_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    primary_id, p_id = _make_product(client_a)
    alt_id = client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    offer_id = client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 5.0,
    }).get_json()["offer"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.put(f"/api/catalog/products/{p_id}/offers/{offer_id}", json={"price": 1.0})
    assert resp.status_code == 403


def test_offer_delete_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    primary_id, p_id = _make_product(client_a)
    alt_id = client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    offer_id = client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 5.0,
    }).get_json()["offer"]["id"]

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.delete(f"/api/catalog/products/{p_id}/offers/{offer_id}")
    assert resp.status_code == 403


def test_offer_update_isolated_by_tenant(logged_in_client_a, logged_in_client_b):
    """Tenant B must not be able to update/delete Tenant A's offer even by
    guessing its numeric id."""
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    offer_id = logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={
        "supplier_id": alt_id, "price": 5.0,
    }).get_json()["offer"]["id"]

    resp = logged_in_client_b.put(f"/api/catalog/products/{p_id}/offers/{offer_id}", json={"price": 1.0})
    assert resp.status_code == 404

    resp = logged_in_client_b.delete(f"/api/catalog/products/{p_id}/offers/{offer_id}")
    assert resp.status_code == 404


def test_deleting_product_removes_its_offers_via_real_api(logged_in_client_a):
    """Same cascade check as the supplier one, but through the actual
    reachable DELETE /products/<id> route (there is no DELETE /suppliers
    route in this app, so that direction is only reachable at the ORM
    level, not through the API)."""
    primary_id, p_id = _make_product(logged_in_client_a)
    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Alt"}).get_json()["supplier"]["id"]
    logged_in_client_a.post(f"/api/catalog/products/{p_id}/offers", json={"supplier_id": alt_id, "price": 5.0})

    resp = logged_in_client_a.delete(f"/api/catalog/products/{p_id}")
    assert resp.status_code == 200
    # The product is gone, so its offers sub-resource is unreachable — this
    # confirms via the API surface that nothing about it is still live.
    assert logged_in_client_a.get(f"/api/catalog/products/{p_id}/offers").status_code == 404


def test_changing_or_deleting_offer_never_affects_existing_orders(logged_in_client_a, make_order):
    """Historical safety: an order's frozen numbers must be completely
    independent of the SupplierProductOffer table, which OrderService never
    reads. Editing or deleting an alternate-supplier offer after an order
    was placed must not alter that order in any way."""
    resp, supplier_id, product_id = make_order(logged_in_client_a, quantity=3, price=10.0, supplier_name="OrderSupplier", product_name="OrderProduct")
    assert resp.status_code == 201
    order = resp.get_json()["order"]
    order_id = order["id"]
    assert order["final_total"] == 30.0

    alt_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "AltForHistTest"}).get_json()["supplier"]["id"]
    offer_id = logged_in_client_a.post(f"/api/catalog/products/{product_id}/offers", json={
        "supplier_id": alt_id, "price": 999.0,
    }).get_json()["offer"]["id"]

    # Change the offer price drastically
    logged_in_client_a.put(f"/api/catalog/products/{product_id}/offers/{offer_id}", json={"price": 1.0})
    unchanged = logged_in_client_a.get(f"/api/orders/{order_id}").get_json()["order"]
    assert unchanged["final_total"] == 30.0
    assert unchanged["items"][0]["unit_price"] == 10.0

    # Delete the offer entirely
    logged_in_client_a.delete(f"/api/catalog/products/{product_id}/offers/{offer_id}")
    still_unchanged = logged_in_client_a.get(f"/api/orders/{order_id}").get_json()["order"]
    assert still_unchanged["final_total"] == 30.0
    assert still_unchanged["items"][0]["unit_price"] == 10.0
