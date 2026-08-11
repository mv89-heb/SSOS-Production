import pytest
from sqlalchemy.exc import IntegrityError


def test_product_sku_is_unique_within_tenant(logged_in_client_a):
    supplier = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier A"}
    ).get_json()["supplier"]

    first = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 1", "sku": "SKU-001", "current_price": 10},
    )
    assert first.status_code == 201

    second = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 2", "sku": "SKU-001", "current_price": 12},
    )
    assert second.status_code in (400, 409, 422, 500)


def test_product_barcode_is_unique_within_tenant(logged_in_client_a):
    supplier = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier A"}
    ).get_json()["supplier"]

    first = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 1", "barcode": "729000000001", "current_price": 10},
    )
    assert first.status_code == 201

    second = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 2", "barcode": "729000000001", "current_price": 12},
    )
    assert second.status_code in (400, 409, 422, 500)


def test_same_sku_is_allowed_across_tenants(logged_in_client_a, logged_in_client_b):
    supplier_a = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier A"}
    ).get_json()["supplier"]
    supplier_b = logged_in_client_b.post(
        "/api/catalog/suppliers", json={"name": "Supplier B"}
    ).get_json()["supplier"]

    first = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier_a["id"], "name": "Tenant A Product", "sku": "SHARED-001", "current_price": 10},
    )
    assert first.status_code == 201

    second = logged_in_client_b.post(
        "/api/catalog/products",
        json={"supplier_id": supplier_b["id"], "name": "Tenant B Product", "sku": "SHARED-001", "current_price": 20},
    )
    assert second.status_code == 201


def test_empty_identifiers_do_not_become_unique_constraints(logged_in_client_a):
    supplier = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier A"}
    ).get_json()["supplier"]

    first = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 1", "sku": "", "barcode": "", "current_price": 10},
    )
    second = logged_in_client_a.post(
        "/api/catalog/products",
        json={"supplier_id": supplier["id"], "name": "Product 2", "sku": "", "barcode": "", "current_price": 12},
    )

    assert first.status_code == 201
    assert second.status_code == 201
