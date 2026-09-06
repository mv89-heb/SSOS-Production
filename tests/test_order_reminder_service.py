from datetime import datetime, timezone

import pytest

from app.services.order_reminder_service import OrderReminderService


def test_build_rules_and_plan_next_window():
    rules = OrderReminderService.build_rules(
        order_days=[3, 6],
        opens_at="08:00",
        closes_at="16:00",
        remind_minutes_before_close=[360, 180, 60, 30, 10],
    )
    now = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)  # Thursday
    points = OrderReminderService.plan_reminders(now, rules)

    assert [point.at for point in points] == [
        datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 3, 13, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 3, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 3, 15, 30, tzinfo=timezone.utc),
        datetime(2026, 9, 3, 15, 50, tzinfo=timezone.utc),
    ]
    assert points[-1].level == "critical"


def test_future_window_is_selected_when_today_has_no_window():
    rules = OrderReminderService.build_rules(
        order_days=[6], opens_at="08:00", closes_at="14:00", remind_minutes_before_close=[60, 10]
    )
    now = datetime(2026, 9, 3, 17, 0, tzinfo=timezone.utc)
    close = OrderReminderService.next_window_close(now, rules)
    assert close == datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)


def test_reminders_before_open_are_omitted():
    rules = OrderReminderService.build_rules(
        order_days=[3], opens_at="08:00", closes_at="16:00", remind_minutes_before_close=[600, 120, 30]
    )
    now = datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc)  # Wednesday
    points = OrderReminderService.plan_reminders(now, rules)
    assert [point.at for point in points] == [
        datetime(2026, 9, 2, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 2, 15, 30, tzinfo=timezone.utc),
    ]


def test_invalid_window_is_rejected():
    with pytest.raises(ValueError):
        OrderReminderService.build_rules(order_days=[3], opens_at="16:00", closes_at="08:00")
