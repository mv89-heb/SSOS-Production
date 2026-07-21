def test_create_order_computes_totals(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a, quantity=100, price=0.15)
    assert resp.status_code == 201
    order = resp.get_json()["order"]
    assert order["subtotal"] == 15.0
    assert order["final_total"] == 15.0
    assert order["status"] == "draft"
    assert order["order_number"].startswith("PO-")


def test_create_order_requires_supplier(logged_in_client_a):
    resp = logged_in_client_a.post("/api/orders", json={"items": [{"product_id": 1, "quantity": 1}]})
    assert resp.status_code == 404


def test_create_order_requires_items(logged_in_client_a):
    s = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Sup"})
    supplier_id = s.get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/orders", json={"supplier_id": supplier_id, "items": []})
    assert resp.status_code == 400


def test_create_order_requires_login(client):
    resp = client.post("/api/orders", json={"supplier_id": 1, "items": [{"product_id": 1, "quantity": 1}]})
    assert resp.status_code == 401


def test_list_orders_returns_created_order(logged_in_client_a, make_order):
    make_order(logged_in_client_a)
    resp = logged_in_client_a.get("/api/orders")
    assert resp.status_code == 200
    assert len(resp.get_json()["orders"]) == 1


def test_list_orders_filters_by_status(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")

    submitted = logged_in_client_a.get("/api/orders?status=submitted")
    drafts = logged_in_client_a.get("/api/orders?status=draft")
    assert len(submitted.get_json()["orders"]) == 1
    assert len(drafts.get_json()["orders"]) == 0


def test_list_orders_rejects_unknown_status(logged_in_client_a):
    resp = logged_in_client_a.get("/api/orders?status=bogus")
    assert resp.status_code == 400


def test_get_single_order(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    fetched = logged_in_client_a.get(f"/api/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["order"]["id"] == order_id


def test_get_nonexistent_order_404(logged_in_client_a):
    resp = logged_in_client_a.get("/api/orders/999999")
    assert resp.status_code == 404


def test_update_draft_order_notes(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    updated = logged_in_client_a.put(f"/api/orders/{order_id}", json={"notes": "urgent"})
    assert updated.status_code == 200
    assert updated.get_json()["order"]["notes"] == "urgent"


def test_update_order_rejects_status_field(logged_in_client_a, make_order):
    """Status changes must go through the lifecycle endpoints, not PUT."""
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    updated = logged_in_client_a.put(f"/api/orders/{order_id}", json={"status": "submitted"})
    assert updated.status_code == 400


def test_submit_order_freezes_snapshot(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a, quantity=2, price=50.0)
    order_id = resp.get_json()["order"]["id"]
    submitted = logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    assert submitted.status_code == 200
    order = submitted.get_json()["order"]
    assert order["status"] == "submitted"
    assert order["snapshot"] is not None
    assert order["snapshot"]["final_total"] == order["final_total"] == 100.0


def test_submit_twice_rejected(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    second = logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    assert second.status_code == 409


def test_full_lifecycle_draft_to_completed(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]

    assert logged_in_client_a.post(f"/api/orders/{order_id}/submit").status_code == 200
    assert logged_in_client_a.post(f"/api/orders/{order_id}/approve").status_code == 200
    assert logged_in_client_a.post(f"/api/orders/{order_id}/sent").status_code == 200
    completed = logged_in_client_a.post(f"/api/orders/{order_id}/complete")
    assert completed.status_code == 200
    assert completed.get_json()["order"]["status"] == "completed"


def test_approve_before_submit_rejected(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    approved = logged_in_client_a.post(f"/api/orders/{order_id}/approve")
    assert approved.status_code == 409


def test_reject_stores_reason_and_cancels(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    rejected = logged_in_client_a.post(f"/api/orders/{order_id}/reject", json={"reason": "price too high"})
    assert rejected.status_code == 200
    order = rejected.get_json()["order"]
    assert order["status"] == "cancelled"
    assert "price too high" in order["notes"]


def test_completed_order_cannot_be_edited(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    logged_in_client_a.post(f"/api/orders/{order_id}/approve")
    logged_in_client_a.post(f"/api/orders/{order_id}/sent")
    logged_in_client_a.post(f"/api/orders/{order_id}/complete")

    blocked = logged_in_client_a.put(f"/api/orders/{order_id}", json={"notes": "too late"})
    assert blocked.status_code == 409


def test_delete_draft_order_succeeds(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    deleted = logged_in_client_a.delete(f"/api/orders/{order_id}")
    assert deleted.status_code == 200
    assert logged_in_client_a.get(f"/api/orders/{order_id}").status_code == 404


def test_delete_submitted_order_blocked(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")
    deleted = logged_in_client_a.delete(f"/api/orders/{order_id}")
    assert deleted.status_code == 409


def test_order_with_unknown_product_404(logged_in_client_a):
    s = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Sup"})
    supplier_id = s.get_json()["supplier"]["id"]
    resp = logged_in_client_a.post("/api/orders", json={
        "supplier_id": supplier_id,
        "items": [{"product_id": 999999, "quantity": 1}],
    })
    assert resp.status_code == 404


def test_order_audit_events_created(logged_in_client_a, make_order):
    resp, _, _ = make_order(logged_in_client_a)
    order_id = resp.get_json()["order"]["id"]
    logged_in_client_a.post(f"/api/orders/{order_id}/submit")

    logs = logged_in_client_a.get("/api/audit").get_json()["logs"]
    actions = [log["action"] for log in logs]
    assert "order.created" in actions
    assert "order.submitted" in actions
