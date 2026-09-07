from datetime import datetime, timezone

from app.services.order_reminder_service import OrderReminderService


def test_plan_reminders_empty_windows_returns_no_points():
    now = datetime.now(timezone.utc)
    assert OrderReminderService.plan_reminders(now, {"windows": {}, "remind_minutes_before_close": [60]}) == []


def test_plan_reminders_valid_window_produces_future_point():
    now = datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc)
    rules = {
        "windows": {"0": {"open": "08:00", "close": "16:00"}},
        "remind_minutes_before_close": [60],
    }
    points = OrderReminderService.plan_reminders(now, rules)
    assert len(points) == 1
    assert points[0].at == datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)
