def test_order_search_filters_supplier_scope_and_returns_pagination(
    logged_in_client_a, make_order
):
    first, _, _ = make_order(
        logged_in_client_a, supplier_name="מאפיית ירושלים", sku="SEARCH-ONE"
    )
    first_order = first.get_json()["order"]
    updated = logged_in_client_a.put(
        f"/api/orders/{first_order['id']}",
        json={"department": "מטבח", "project": "שבת"},
    )
    assert updated.status_code == 200

    second, _, _ = make_order(
        logged_in_client_a, supplier_name="ירקות הצפון", sku="SEARCH-TWO"
    )
    assert second.status_code == 201

    response = logged_in_client_a.get(
        "/api/orders/search?q=ירושלים&status=draft&limit=1&offset=0"
    )
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["pagination"] == {
        "total": 1, "limit": 1, "offset": 0, "has_more": False
    }
    assert [order["id"] for order in payload["orders"]] == [first_order["id"]]

    project_search = logged_in_client_a.get("/api/orders/search?q=שבת")
    assert project_search.status_code == 200
    assert [order["id"] for order in project_search.get_json()["orders"]] == [first_order["id"]]


def test_order_search_is_tenant_scoped(
    logged_in_client_a, logged_in_client_b, make_order
):
    first, _, _ = make_order(
        logged_in_client_a, supplier_name="ספק פרטי אלפא", sku="TENANT-ALPHA"
    )
    second, _, _ = make_order(
        logged_in_client_b, supplier_name="ספק פרטי אלפא", sku="TENANT-BETA"
    )
    assert first.status_code == 201
    assert second.status_code == 201

    response = logged_in_client_b.get("/api/orders/search?q=אלפא")
    assert response.status_code == 200, response.get_json()
    orders = response.get_json()["orders"]
    assert len(orders) == 1
    assert orders[0]["id"] == second.get_json()["order"]["id"]


def test_order_search_validates_filters_and_limits(
    logged_in_client_a, make_order
):
    make_order(logged_in_client_a)

    assert logged_in_client_a.get("/api/orders/search?status=unknown").status_code == 400
    assert logged_in_client_a.get("/api/orders/search?supplier_id=bad").status_code == 400
    assert logged_in_client_a.get("/api/orders/search?start_date=2026-11-20&end_date=2026-11-01").status_code == 400
    assert logged_in_client_a.get("/api/orders/search?q=" + ("א" * 201)).status_code == 400

    capped = logged_in_client_a.get("/api/orders/search?limit=500")
    assert capped.status_code == 200
    assert capped.get_json()["pagination"]["limit"] == 100


def test_order_search_requires_authentication(client):
    response = client.get("/api/orders/search?q=test")
    assert response.status_code == 401


def test_order_search_matches_product_name_and_sku(
    logged_in_client_a, make_order
):
    response, _, _ = make_order(
        logged_in_client_a,
        supplier_name="ספק מוצר",
        product_name="גבינה לבנה 5%",
        sku="DAIRY-005",
    )
    assert response.status_code == 201, response.get_json()

    by_name = logged_in_client_a.get("/api/orders/search?q=גבינה+לבנה")
    assert by_name.status_code == 200, by_name.get_json()
    assert [item["id"] for item in by_name.get_json()["orders"]] == [
        response.get_json()["order"]["id"]
    ]

    by_sku = logged_in_client_a.get("/api/orders/search?q=DAIRY-005")
    assert by_sku.status_code == 200, by_sku.get_json()
    assert [item["id"] for item in by_sku.get_json()["orders"]] == [
        response.get_json()["order"]["id"]
    ]


def test_order_search_csv_export_preserves_hebrew_and_applies_filters(
    logged_in_client_a, make_order
):
    supplier_name = "מאפיית ירושלים"
    response, _, _ = make_order(
        logged_in_client_a,
        supplier_name=supplier_name,
        product_name="לחם אחיד",
        sku="BREAD-001",
    )
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    updated = logged_in_client_a.put(
        f"/api/orders/{order_id}",
        json={"department": "=SUM(1,1)"},
    )
    assert updated.status_code == 200, updated.get_json()

    exported = logged_in_client_a.get("/api/orders/search?format=csv&q=לחם+אחיד")
    assert exported.status_code == 200
    assert exported.mimetype == "text/csv"
    assert exported.headers["X-Export-Row-Count"] == "1"

    import csv
    import io

    body = exported.get_data(as_text=True)
    assert body.startswith("\ufeff")
    rows = list(csv.reader(io.StringIO(body.lstrip("\ufeff"))))
    assert rows[0] == [
        "מספר הזמנה", "ספק", "סטטוס", "מחלקה", "פרויקט",
        "תאריך יצירה", "תאריך הזמנה מתוכנן", "מטבע", 'סה"כ', "פריטים",
    ]
    assert len(rows) == 2
    assert rows[1][1] == supplier_name
    assert rows[1][3] == "'=SUM(1,1)"
    assert "לחם אחיד" in rows[1][9]


def test_order_search_csv_export_is_tenant_scoped(
    logged_in_client_a, logged_in_client_b, make_order
):
    response, _, _ = make_order(
        logged_in_client_a,
        supplier_name="ספק פרטי לייצוא",
        product_name="מוצר חסוי",
        sku="PRIVATE-EXPORT",
    )
    assert response.status_code == 201

    exported = logged_in_client_b.get(
        "/api/orders/search?format=csv&q=מוצר+חסוי"
    )
    assert exported.status_code == 200
    assert exported.headers["X-Export-Row-Count"] == "0"


def test_order_search_csv_export_rejects_oversized_result(
    logged_in_client_a, make_order, monkeypatch
):
    first, _, _ = make_order(logged_in_client_a, sku="EXPORT-LIMIT-ONE")
    second, _, _ = make_order(logged_in_client_a, sku="EXPORT-LIMIT-TWO")
    assert first.status_code == 201
    assert second.status_code == 201

    monkeypatch.setattr("app.routes.order_search.MAX_EXPORT_ROWS", 1)
    exported = logged_in_client_a.get("/api/orders/search?format=csv")
    assert exported.status_code == 413
    assert exported.get_json()["error"] == "export_too_large"


def test_order_search_csv_export_does_not_silently_truncate(
    logged_in_client_a, make_order
):
    first, _, _ = make_order(
        logged_in_client_a, product_name="לחם אחיד", sku="BREAD-EXPORT-1"
    )
    second, _, _ = make_order(
        logged_in_client_a, product_name="לחם שיפון", sku="BREAD-EXPORT-2"
    )
    assert first.status_code == 201
    assert second.status_code == 201

    exported = logged_in_client_a.get(
        "/api/orders/search?format=csv&limit=1&q=לחם"
    )
    assert exported.status_code == 200
    assert exported.headers["X-Export-Row-Count"] == "2"


def test_saved_order_search_crud_and_filter_normalization(logged_in_client_a):
    created = logged_in_client_a.post(
        "/api/orders/searches",
        json={
            "name": "  הזמנות חלב  ",
            "filters": {
                "q": "  חלב  ",
                "status": "submitted",
                "start_date": "2026-11-01",
                "end_date": "2026-11-18",
            },
        },
    )
    assert created.status_code == 201, created.get_json()
    saved = created.get_json()["saved_search"]
    assert saved["name"] == "הזמנות חלב"
    assert saved["filters"] == {
        "q": "חלב",
        "status": "submitted",
        "supplier_id": None,
        "start_date": "2026-11-01",
        "end_date": "2026-11-18",
    }

    listed = logged_in_client_a.get("/api/orders/searches")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()["saved_searches"]] == [saved["id"]]

    deleted = logged_in_client_a.delete(f"/api/orders/searches/{saved['id']}")
    assert deleted.status_code == 200
    assert logged_in_client_a.get("/api/orders/searches").get_json()["saved_searches"] == []


def test_saved_order_search_is_tenant_scoped(
    logged_in_client_a, logged_in_client_b
):
    created = logged_in_client_a.post(
        "/api/orders/searches",
        json={"name": "חיפוש פרטי", "filters": {"q": "סודי"}},
    )
    assert created.status_code == 201
    saved_id = created.get_json()["saved_search"]["id"]

    assert logged_in_client_b.get("/api/orders/searches").get_json()["saved_searches"] == []
    forbidden_delete = logged_in_client_b.delete(f"/api/orders/searches/{saved_id}")
    assert forbidden_delete.status_code == 404


def test_saved_order_search_rejects_invalid_filters_and_duplicate_names(
    logged_in_client_a
):
    valid_payload = {"name": "חיפוש תקין", "filters": {"q": "ספק"}}
    assert logged_in_client_a.post("/api/orders/searches", json=valid_payload).status_code == 201

    duplicate = logged_in_client_a.post(
        "/api/orders/searches",
        json={"name": "  חיפוש תקין  ", "filters": {}},
    )
    assert duplicate.status_code == 409

    invalid_payloads = [
        {"name": "ארוך", "filters": {"q": "א" * 201}},
        {"name": "סטטוס", "filters": {"status": "unknown"}},
        {"name": "מפתח", "filters": {"raw_sql": "select * from orders"}},
        {"name": "תאריכים", "filters": {"start_date": "2026-11-20", "end_date": "2026-11-01"}},
        {"name": "טווח", "filters": {"start_date": "2020-01-01", "end_date": "2026-11-01"}},
    ]
    for payload in invalid_payloads:
        response = logged_in_client_a.post("/api/orders/searches", json=payload)
        assert response.status_code == 400, response.get_json()


def test_saved_order_search_limit_is_enforced(logged_in_client_a):
    for index in range(20):
        response = logged_in_client_a.post(
            "/api/orders/searches",
            json={"name": f"חיפוש {index + 1}", "filters": {}},
        )
        assert response.status_code == 201, response.get_json()

    limited = logged_in_client_a.post(
        "/api/orders/searches",
        json={"name": "חיפוש 21", "filters": {}},
    )
    assert limited.status_code == 409


def test_saved_order_search_requires_authentication(client):
    assert client.get("/api/orders/searches").status_code == 401
    assert client.post(
        "/api/orders/searches", json={"name": "לא מחובר", "filters": {}}
    ).status_code == 401


def test_saved_order_search_is_private_to_its_creator(logged_in_client_a, db):
    from sqlalchemy import select
    from app.models.user import User, ROLE_ADMIN

    admin = db.session.scalar(select(User).where(User.email == "admin@acme.test"))
    other_user = User(
        tenant_id=admin.tenant_id,
        email="second-admin@acme.test",
        full_name="Second Admin",
        role=ROLE_ADMIN,
        active=True,
    )
    other_user.set_password("Passw0rd1")
    db.session.add(other_user)
    db.session.commit()

    created = logged_in_client_a.post(
        "/api/orders/searches",
        json={"name": "החיפוש שלי", "filters": {"q": "פרטי"}},
    )
    assert created.status_code == 201

    other_client = logged_in_client_a.application.test_client()
    login = other_client.post(
        "/api/auth/login",
        json={"email": "second-admin@acme.test", "password": "Passw0rd1"},
    )
    assert login.status_code == 200
    assert other_client.get("/api/orders/searches").get_json()["saved_searches"] == []
