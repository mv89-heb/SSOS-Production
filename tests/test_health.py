def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["application"] == "SSOS"
    assert body["status"] == "running"


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_health_ready_endpoint(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"


def test_health_endpoints_do_not_require_auth(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 200
