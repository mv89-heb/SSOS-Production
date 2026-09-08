from datetime import datetime, timezone


def test_activate_reminder_survives_google_calendar_failure(monkeypatch, logged_in_client_a, make_order, db):
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
    assert payload["order"]["reminder_rules_snapshot"]["recurrence"]["every_minutes"] == 60
    assert payload["ai"]["urgency"] in {"low", "normal", "high", "critical"}


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


def test_ai_analysis_uses_deterministic_urgency_baseline(logged_in_client_a, make_order, db):
    response, _, _ = make_order(logged_in_client_a, supplier_name="Urgent Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]
    from app.models.order import Order
    order = db.session.get(Order, order_id)
    order.notes = "דחוף, זה עוצר עבודה"
    db.session.commit()

    result = logged_in_client_a.post(
        f"/api/order-reminders/orders/{order_id}/ai-analysis",
        json={"text": "חייבים את זה היום אחרת העבודה נעצרת"},
    )
    assert result.status_code == 200, result.get_json()
    payload = result.get_json()
    assert payload["success"] is True
    assert payload["ai"]["score"] >= 55
    assert payload["ai"]["urgency"] in {"high", "critical"}
    assert payload["display"]["emoji"] in {"🟠", "🔴"}


def test_natural_language_reminder_returns_bounded_plan(logged_in_client_a, make_order):
    response, _, _ = make_order(logged_in_client_a, supplier_name="Natural Language Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    result = logged_in_client_a.post(
        f"/api/order-reminders/orders/{order_id}/natural-language",
        json={"text": "תזכיר לי בעוד שעה ותמשיך להזכיר לי כל שעה עד שאטפל בזה"},
    )
    assert result.status_code == 200, result.get_json()
    payload = result.get_json()
    assert payload["success"] is True
    assert payload["applied"] is False
    assert 5 <= payload["ai"]["first_reminder_minutes"] <= 10080
    assert 5 <= payload["ai"]["repeat_minutes"] <= 10080
    assert payload["ai"]["interpretation"]
