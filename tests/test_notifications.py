def test_create_notification(logged_in_client_a):
    resp = logged_in_client_a.post("/api/notifications", json={"title": "Hello", "message": "World"})
    assert resp.status_code == 201
    body = resp.get_json()["notification"]
    assert body["title"] == "Hello"
    assert body["status"] == "unread"


def test_create_notification_requires_title(logged_in_client_a):
    resp = logged_in_client_a.post("/api/notifications", json={"message": "no title"})
    assert resp.status_code == 400


def test_list_notifications(logged_in_client_a):
    logged_in_client_a.post("/api/notifications", json={"title": "N1"})
    logged_in_client_a.post("/api/notifications", json={"title": "N2"})
    resp = logged_in_client_a.get("/api/notifications")
    assert resp.status_code == 200
    assert len(resp.get_json()["notifications"]) == 2


def test_list_unread_only(logged_in_client_a):
    created = logged_in_client_a.post("/api/notifications", json={"title": "Read me"})
    notif_id = created.get_json()["notification"]["id"]
    logged_in_client_a.post("/api/notifications", json={"title": "Still unread"})

    logged_in_client_a.post(f"/api/notifications/{notif_id}/read")

    resp = logged_in_client_a.get("/api/notifications?unread_only=true")
    titles = [n["title"] for n in resp.get_json()["notifications"]]
    assert "Read me" not in titles
    assert "Still unread" in titles


def test_mark_notification_read(logged_in_client_a):
    created = logged_in_client_a.post("/api/notifications", json={"title": "Mark me"})
    notif_id = created.get_json()["notification"]["id"]

    resp = logged_in_client_a.post(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 200
    assert resp.get_json()["notification"]["status"] == "read"
    assert resp.get_json()["notification"]["read_at"] is not None


def test_mark_nonexistent_notification_404(logged_in_client_a):
    resp = logged_in_client_a.post("/api/notifications/999999/read")
    assert resp.status_code == 404


def test_notifications_require_login(client):
    assert client.get("/api/notifications").status_code == 401
    assert client.post("/api/notifications", json={"title": "x"}).status_code == 401
