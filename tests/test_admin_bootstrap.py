def test_admin_blueprint_is_registered_and_cors_preflight_is_valid(client):
    response = client.options(
        "/api/admin/orders/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert "DELETE" in (response.headers.get("Access-Control-Allow-Methods") or "")
