from datetime import date
from decimal import Decimal

from app.services.inventory_calendar_service import InventoryCalendarService


def test_default_four_week_cycle_uses_three_normal_and_one_boosted_week(monkeypatch):
    monkeypatch.delenv("SSOS_BOOSTED_CYCLE_WEEKS", raising=False)
    monkeypatch.delenv("SSOS_BOOSTED_WEEKS", raising=False)
    monkeypatch.delenv("SSOS_BOOSTED_WEEK_MULTIPLIER", raising=False)

    config = InventoryCalendarService._seasonality_config()
    metrics = InventoryCalendarService._seasonality_metrics(Decimal("1"), config)

    assert config["normal_weeks"] == 3
    assert config["boosted_weeks"] == 1
    assert config["uplift"] == Decimal("1.4")
    assert metrics["normal_weekly_demand"] == 7
    assert metrics["boosted_weekly_demand"] == 9.8
    assert metrics["average_weekly_demand"] == 7.7
    assert metrics["monthly_forecast_demand"] == 30.8
    assert InventoryCalendarService._seasonal_multiplier_for_date(date(2020, 1, 6), config) == 1
    assert InventoryCalendarService._seasonal_multiplier_for_date(date(2020, 1, 27), config) == Decimal("1.4")


def test_seasonal_cycle_is_configurable_and_bounded(monkeypatch):
    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "3")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "1")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "1.5")

    config = InventoryCalendarService._seasonality_config()
    metrics = InventoryCalendarService._seasonality_metrics(Decimal("2"), config)

    assert config["normal_weeks"] == 2
    assert config["boosted_weeks"] == 1
    assert config["uplift"] == Decimal("1.5")
    assert metrics["average_weekly_demand"] == 16.333
    assert InventoryCalendarService._seasonal_multiplier_for_date(date(2020, 1, 20), config) == Decimal("1.5")


def test_invalid_configuration_falls_back_to_safe_defaults(monkeypatch):
    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "invalid")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "99")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "NaN")

    config = InventoryCalendarService._seasonality_config()

    assert config["cycle_weeks"] == 4
    assert config["boosted_weeks"] == 1
    assert config["uplift"] == Decimal("1.4")


def test_seasonality_does_not_invent_consumption_when_no_measurements_exist():
    config = InventoryCalendarService._seasonality_config()
    metrics = InventoryCalendarService._seasonality_metrics(Decimal("0"), config)

    assert metrics["normal_weekly_demand"] == 0
    assert metrics["boosted_weekly_demand"] == 0
    assert metrics["average_weekly_demand"] == 0
    assert metrics["monthly_forecast_demand"] == 0
