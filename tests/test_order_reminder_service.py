from datetime import datetime, timezone

import pytest

from app.services.order_reminder_service import OrderReminderService


def test_build_rules_and_plan_next_window():
    rules = OrderReminderService.build_rules(
        order_days=[4, 6],
        opens_at="08:00",
        closes_at="16:00",
        remind_minutes_before_close=[360, 180, 60, 30, 10],
    )
    now = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)  # Thursday
    points = OrderReminderService.plan_reminders(now, rules)

    assert [point.at.hour for point in points] == [10, 13, 15, 15, 15]
    assert points[-1].level == "critical"


def test_future_window_is_selected_when_today_is_before_open():
    rules = OrderReminderService.build_rules(
        order_days=[6], opens_at="08:00", closes_at="14:00", remind_minutes_before_close=[60, 10]
    )
    now = datetime(2026, 9, 3, 17, 0, tzinfo=timezone.utc)
    close = OrderReminderService.next_window_close(now, rules)
    assert close == datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)


def test_reminders_before_open_are_omitted():
    rules = OrderReminderService.build_rules(
        order_days=[4], opens_at="08:00", closes_at="16:00", remind_minutes_before_close=[600, 120, 30]
    )
    now = datetime(2026, 9, 3, 7, 0, tzinfo=timezone.utc)
    points = OrderReminderService.plan_reminders(now, rules)
    assert [point.at.hour for point in points] == [8, 14, 15,]


def test_invalid_window_is_rejected():
    with pytest.raises(ValueError):
        OrderReminderService.build_rules(order_days=[4], opens_at="16:00", closes_at="08:00")
