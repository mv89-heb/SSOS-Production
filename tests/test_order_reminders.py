from datetime import datetime, timezone


def test_activate_reminder_survives_google_calendar_failure(monkeypatch, logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, supplier_name="Calendar Failure Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    def fail_sync(_order):
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr("app.routes.order_reminders.gcal.sync_order_event", fail_sync)

    activated = logged_in_client_a.post(f"/api/order-reminders/orders/{order_id}/activate")
    assert activated.status_code == 200, activated.get_json()
    payload = activated.get_json()
    assert payload["success"] is True
    assert payload["order"]["reminder_state"] == "pending"
    assert payload["order"]["next_reminder_at"] is not None
    assert payload["calendar_event_id"] is None


def test_complete_reminder_survives_google_calendar_failure(monkeypatch, logged_in_client_a, make_order, db):
    response, _, _ = make_order(logged_in_client_a, supplier_name="Complete Calendar Failure Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    activated = logged_in_client_a.post(f"/api/order-reminders/orders/{order_id}/activate")
    assert activated.status_code == 200, activated.get_json()

    def fail_delete(_order):
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr("app.routes.order_reminders.gcal.delete_order_event", fail_delete)

    completed = logged_in_client_a.post(f"/api/order-reminders/orders/{order_id}/complete")
    assert completed.status_code == 200, completed.get_json()
    assert completed.get_json()["order"]["reminder_state"] == "complete"

    from app.models.order import Order, REMINDER_COMPLETE

    order = db.session.get(Order, order_id)
    assert order.reminder_state == REMINDER_COMPLETE
    assert order.next_reminder_at is None


def test_manual_reminder_rejects_past_datetime(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, supplier_name="Manual Reminder Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    result = logged_in_client_a.post(
        f"/api/order-reminders/orders/{order_id}/manual",
        json={"reminder_at": datetime.now(timezone.utc).isoformat()},
    )
    assert result.status_code == 400
    assert result.get_json()["success"] is False
