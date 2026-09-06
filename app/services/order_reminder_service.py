"""Supplier-aware order reminder planning.

The planner is intentionally side-effect free: it determines the next useful
reminder times from a supplier's ordering rules without sending notifications.
A reminder remains open until the related order is explicitly marked sent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class ReminderPoint:
    """One reminder scheduled before a supplier ordering-window close."""

    at: datetime
    level: str
    label: str


@dataclass(frozen=True)
class OrderingWindow:
    """A supplier ordering window for one weekday."""

    weekday: int  # Monday=0 ... Sunday=6
    opens_at: time
    closes_at: time

    def contains(self, value: datetime) -> bool:
        local = value.astimezone(timezone.utc)
        current = local.time().replace(tzinfo=None)
        return self.opens_at <= current < self.closes_at


class OrderReminderService:
    """Calculate persistent, supplier-aware order reminders.

    Rules are represented as a small JSON-friendly mapping so existing
    supplier records remain backward compatible. Example::

        {
          "timezone": "UTC",
          "windows": {
            "4": {"open": "08:00", "close": "16:00"},
            "6": {"open": "08:00", "close": "14:00"}
          },
          "remind_minutes_before_close": [360, 180, 60, 30, 10]
        }

    Weekday keys use Python's ``datetime.weekday()`` convention.
    """

    DEFAULT_MINUTES = (360, 180, 60, 30, 10)

    @classmethod
    def parse_time(cls, value: str) -> time:
        hour, minute = (int(part) for part in value.strip().split(":", 1))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("time must be HH:MM")
        return time(hour=hour, minute=minute)

    @classmethod
    def windows_from_rules(cls, rules: dict) -> list[OrderingWindow]:
        windows = rules.get("windows", {}) if isinstance(rules, dict) else {}
        result: list[OrderingWindow] = []
        for raw_day, raw_window in windows.items():
            weekday = int(raw_day)
            if weekday < 0 or weekday > 6:
                raise ValueError("weekday must be between 0 and 6")
            opens = cls.parse_time(str(raw_window["open"]))
            closes = cls.parse_time(str(raw_window["close"]))
            if opens >= closes:
                raise ValueError("ordering window must open before it closes")
            result.append(OrderingWindow(weekday, opens, closes))
        return sorted(result, key=lambda item: item.weekday)

    @classmethod
    def next_window_close(
        cls,
        now: datetime,
        rules: dict,
        horizon_days: int = 14,
    ) -> datetime | None:
        """Return the next active/eligible ordering-window close."""
        windows = cls.windows_from_rules(rules)
        if not windows:
            return None
        anchor = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        for offset in range(horizon_days + 1):
            day = (anchor + timedelta(days=offset)).date()
            weekday = day.weekday()
            for window in windows:
                if window.weekday != weekday:
                    continue
                close = datetime.combine(day, window.closes_at, tzinfo=anchor.tzinfo)
                if close <= anchor:
                    continue
                open_dt = datetime.combine(day, window.opens_at, tzinfo=anchor.tzinfo)
                if offset == 0 and anchor < open_dt:
                    return close
                if open_dt <= anchor < close:
                    return close
                if offset > 0:
                    return close
        return None

    @classmethod
    def plan_reminders(
        cls,
        now: datetime,
        rules: dict,
        *,
        minutes_before_close: Iterable[int] | None = None,
    ) -> list[ReminderPoint]:
        """Plan reminders for the next order window.

        The last reminder is always inside the supplier window when possible;
        reminders that fall before opening are omitted. This supports the
        requested "never forget" behavior without generating useless alerts
        after the supplier has closed.
        """
        close = cls.next_window_close(now, rules)
        if close is None:
            return []
        windows = cls.windows_from_rules(rules)
        active_window = next((w for w in windows if w.weekday == close.weekday()), None)
        if active_window is None:
            return []
        open_dt = datetime.combine(close.date(), active_window.opens_at, tzinfo=close.tzinfo)
        minute_values = sorted(
            {int(value) for value in (minutes_before_close or rules.get("remind_minutes_before_close", cls.DEFAULT_MINUTES)) if int(value) >= 0},
            reverse=True,
        )
        points: list[ReminderPoint] = []
        for minutes in minute_values:
            at = close - timedelta(minutes=minutes)
            if at < open_dt or at < now:
                continue
            if minutes >= 180:
                level = "upcoming"
            elif minutes >= 60:
                level = "due"
            elif minutes >= 15:
                level = "urgent"
            else:
                level = "critical"
            label = "Order supplier" if minutes == 0 else f"Order supplier — {minutes}m before close"
            points.append(ReminderPoint(at=at, level=level, label=label))
        return sorted(points, key=lambda point: point.at)

    @classmethod
    def build_rules(
        cls,
        *,
        order_days: Iterable[int],
        opens_at: str = "08:00",
        closes_at: str = "16:00",
        remind_minutes_before_close: Iterable[int] | None = None,
    ) -> dict:
        """Build a normalized rules document for persistence."""
        open_value = cls.parse_time(opens_at)
        close_value = cls.parse_time(closes_at)
        if open_value >= close_value:
            raise ValueError("ordering window must open before it closes")
        days = sorted({int(day) for day in order_days})
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("weekday must be between 0 and 6")
        reminders = sorted(
            {int(value) for value in (remind_minutes_before_close or cls.DEFAULT_MINUTES) if int(value) >= 0},
            reverse=True,
        )
        return {
            "windows": {
                str(day): {"open": opens_at, "close": closes_at}
                for day in days
            },
            "remind_minutes_before_close": reminders,
        }
