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
