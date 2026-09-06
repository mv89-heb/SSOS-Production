"""Supplier-aware order reminder planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class ReminderPoint:
    at: datetime
    level: str
    label: str


@dataclass(frozen=True)
class OrderingWindow:
    weekday: int
    opens_at: time
    closes_at: time


class OrderReminderService:
    """Calculate persistent, supplier-aware order reminders."""

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
            if not 0 <= weekday <= 6:
                raise ValueError("weekday must be between 0 and 6")
            opens = cls.parse_time(str(raw_window["open"]))
            closes = cls.parse_time(str(raw_window["close"]))
            if opens >= closes:
                raise ValueError("ordering window must open before it closes")
            result.append(OrderingWindow(weekday, opens, closes))
        return sorted(result, key=lambda item: item.weekday)

    @classmethod
    def next_window(
        cls, now: datetime, rules: dict, horizon_days: int = 14
    ) -> tuple[datetime, datetime] | None:
        windows = cls.windows_from_rules(rules)
        if not windows:
            return None
        anchor = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        for offset in range(horizon_days + 1):
            day = (anchor + timedelta(days=offset)).date()
            for window in windows:
                if window.weekday != day.weekday():
                    continue
                open_dt = datetime.combine(day, window.opens_at, tzinfo=anchor.tzinfo)
                close_dt = datetime.combine(day, window.closes_at, tzinfo=anchor.tzinfo)
                if close_dt <= anchor:
                    continue
                if offset > 0 or anchor < close_dt:
                    return open_dt, close_dt
        return None

    @classmethod
    def next_window_close(
        cls, now: datetime, rules: dict, horizon_days: int = 14
    ) -> datetime | None:
        window = cls.next_window(now, rules, horizon_days=horizon_days)
        return window[1] if window else None

    @classmethod
    def plan_reminders(
        cls,
        now: datetime,
        rules: dict,
        *,
        minutes_before_close: Iterable[int] | None = None,
    ) -> list[ReminderPoint]:
        window = cls.next_window(now, rules)
        if window is None:
            return []
        open_dt, close = window
        raw_values = (
            minutes_before_close
            if minutes_before_close is not None
            else rules.get("remind_minutes_before_close", cls.DEFAULT_MINUTES)
        )
        try:
            minute_values = sorted({int(value) for value in raw_values if int(value) >= 0}, reverse=True)
        except (TypeError, ValueError):
            raise ValueError("remind_minutes_before_close must contain integers")

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
        timezone_name: str = "UTC",
    ) -> dict:
        open_value = cls.parse_time(opens_at)
        close_value = cls.parse_time(closes_at)
        if open_value >= close_value:
            raise ValueError("ordering window must open before it closes")
        days = sorted({int(day) for day in order_days})
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("weekday must be between 0 and 6")
        reminders_source = (
            remind_minutes_before_close
            if remind_minutes_before_close is not None
            else cls.DEFAULT_MINUTES
        )
        try:
            reminders = sorted({int(value) for value in reminders_source if int(value) >= 0}, reverse=True)
        except (TypeError, ValueError):
            raise ValueError("remind_minutes_before_close must contain integers")
        return {
            "timezone": str(timezone_name),
            "windows": {str(day): {"open": opens_at, "close": closes_at} for day in days},
            "remind_minutes_before_close": reminders,
        }
