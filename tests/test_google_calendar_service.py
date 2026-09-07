from datetime import datetime, timezone

from app import create_app
from app.services import google_calendar_service as gcal


def test_google_calendar_oauth_state_round_trip():
    app = create_app("testing")
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        state = gcal.create_oauth_state(42)
        assert gcal.read_oauth_state(state) == 42


def test_google_calendar_event_payload_uses_local_timezone():
    app = create_app("testing")
    app.config["SECRET_KEY"] = "test-secret"
    app.config["FRONTEND_PUBLIC_URL"] = "https://example.test"
    app.config["GOOGLE_CALENDAR_TIMEZONE"] = "Asia/Jerusalem"

    class Order:
        id = 7
        order_number = "PO-7"
        supplier_name = "ספק בדיקה"
        next_reminder_at = datetime(2026, 9, 7, 7, 0, tzinfo=timezone.utc)

    with app.app_context():
        payload = gcal.event_payload(Order())

    assert payload["summary"] == "מעקב הזמנה PO-7 – ספק בדיקה"
    assert payload["start"]["timeZone"] == "Asia/Jerusalem"
    assert payload["start"]["dateTime"].endswith("+03:00")
    assert "/dashboard/orders/7" in payload["description"]
    assert payload["reminders"]["overrides"][0] == {"method": "popup", "minutes": 10}
