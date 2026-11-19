import pytest
from app.models.inventory_consumption_profile import InventoryConsumptionProfile


def _supplier_and_product(client, name="Supplier A", product_name="Disposable plate"):
    supplier_response = client.post("/api/catalog/suppliers", json={"name": name})
    assert supplier_response.status_code == 201, supplier_response.get_json()
    supplier_id = supplier_response.get_json()["supplier"]["id"]
    product_response = client.post("/api/catalog/products", json={
        "supplier_id": supplier_id,
        "name": product_name,
        "sku": "PROFILE-" + product_name[:12].replace(" ", "-"),
        "current_price": 10,
        "unit": "קרטון",
    })
    assert product_response.status_code == 201, product_response.get_json()
    return supplier_id, product_response.get_json()["product"]["id"]


def test_consumption_profile_calculates_reinforced_three_week_cycle(logged_in_client_a):
    supplier_id, product_id = _supplier_and_product(logged_in_client_a)
    response = logged_in_client_a.post("/api/inventory/planning/profiles", json={
        "name": "צלחות קלקר",
        "category": "חד״פ",
        "supplier_ids": [supplier_id],
        "product_ids": [product_id],
        "min_order_quantity": 5,
        "max_order_quantity": 10,
        "average_order_quantity": 5,
        "regular_weekly_consumption": 2,
        "reinforced_weekly_consumption": 4,
        "reinforcement_cycle_weeks": 3,
        "safety_stock": 4.5,
    })
    assert response.status_code == 201, response.get_json()
    profile = response.get_json()["profile"]
    assert profile["weighted_weekly_consumption"] == pytest.approx(2.6666666667)
    assert profile["monthly_consumption"] == pytest.approx(10.6666666667)
    assert profile["mapping_status"] == "mapped"
    assert profile["product_names"][str(product_id)] == "Disposable plate" or profile["product_names"][product_id] == "Disposable plate"


def test_consumption_profile_rejects_product_from_unselected_supplier(logged_in_client_a):
    supplier_id, product_id = _supplier_and_product(logged_in_client_a)
    other_supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier B"})
    assert other_supplier.status_code == 201
    response = logged_in_client_a.post("/api/inventory/planning/profiles", json={
        "name": "Invalid mapping",
        "category": "חד״פ",
        "supplier_ids": [other_supplier.get_json()["supplier"]["id"]],
        "product_ids": [product_id],
        "min_order_quantity": 1,
        "max_order_quantity": 2,
        "average_order_quantity": 1,
        "regular_weekly_consumption": 1,
        "reinforced_weekly_consumption": 2,
        "reinforcement_cycle_weeks": 3,
        "safety_stock": 1,
    })
    assert response.status_code == 400
    assert "selected suppliers" in response.get_json()["message"]


def test_consumption_profiles_are_tenant_scoped(logged_in_client_a, logged_in_client_b):
    supplier_id, product_id = _supplier_and_product(logged_in_client_a, name="Tenant A Supplier")
    created = logged_in_client_a.post("/api/inventory/planning/profiles", json={
        "name": "Tenant A Profile",
        "category": "חד״פ",
        "supplier_ids": [supplier_id],
        "product_ids": [product_id],
        "min_order_quantity": 1,
        "max_order_quantity": 2,
        "average_order_quantity": 1,
        "regular_weekly_consumption": 1,
        "reinforced_weekly_consumption": 2,
        "reinforcement_cycle_weeks": 3,
        "safety_stock": 1,
    })
    assert created.status_code == 201, created.get_json()
    profile_id = created.get_json()["profile"]["id"]

    assert logged_in_client_b.get("/api/inventory/planning/profiles").get_json()["profiles"] == []
    assert logged_in_client_b.put(
        f"/api/inventory/planning/profiles/{profile_id}",
        json={"name": "Cross tenant edit"},
    ).status_code == 404


def test_consumption_profile_archive_is_non_destructive(logged_in_client_a, db):
    supplier_id, _ = _supplier_and_product(logged_in_client_a, product_name="Archive test")
    created = logged_in_client_a.post("/api/inventory/planning/profiles", json={
        "name": "Archive me",
        "category": "ציוד",
        "supplier_ids": [supplier_id],
        "product_ids": [],
        "min_order_quantity": 1,
        "max_order_quantity": 3,
        "average_order_quantity": 1,
        "regular_weekly_consumption": 0.2,
        "reinforced_weekly_consumption": 0.5,
        "reinforcement_cycle_weeks": 3,
        "safety_stock": 4.5,
    })
    assert created.status_code == 201
    profile_id = created.get_json()["profile"]["id"]

    archived = logged_in_client_a.delete(f"/api/inventory/planning/profiles/{profile_id}")
    assert archived.status_code == 200
    assert logged_in_client_a.get("/api/inventory/planning/profiles").get_json()["profiles"] == []
    stored = db.session.get(InventoryConsumptionProfile, profile_id)
    assert stored is not None
    assert stored.active is False
    assert float(stored.safety_stock) == 4.5
