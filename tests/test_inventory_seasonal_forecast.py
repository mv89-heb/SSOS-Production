from decimal import Decimal

from app.services.inventory_planning_service import InventoryPlanningService


def test_default_four_week_cycle_uses_three_normal_and_one_boosted_week(monkeypatch):
    monkeypatch.delenv("SSOS_BOOSTED_CYCLE_WEEKS", raising=False)
    monkeypatch.delenv("SSOS_BOOSTED_WEEKS", raising=False)
    monkeypatch.delenv("SSOS_BOOSTED_WEEK_MULTIPLIER", raising=False)

    forecast = InventoryPlanningService._seasonal_forecast_metrics(Decimal("1"))

    assert forecast["normal_weeks_per_cycle"] == 3
    assert forecast["boosted_weeks_per_cycle"] == 1
    assert forecast["boosted_week_multiplier"] == 1.4
    assert forecast["normal_weekly_demand"] == 7
    assert forecast["boosted_weekly_demand"] == 9.8
    assert forecast["average_weekly_demand"] == 7.7
    assert forecast["monthly_forecast_demand"] == 30.8


def test_seasonal_cycle_is_configurable_and_bounded(monkeypatch):
    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "3")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "1")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "1.5")

    forecast = InventoryPlanningService._seasonal_forecast_metrics(2)

    assert forecast["normal_weeks_per_cycle"] == 2
    assert forecast["boosted_weeks_per_cycle"] == 1
    assert forecast["boosted_week_multiplier"] == 1.5
    assert forecast["average_weekly_demand"] == 16.333


def test_invalid_configuration_falls_back_to_safe_defaults(monkeypatch):
    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "invalid")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "99")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "NaN")

    forecast = InventoryPlanningService._seasonal_forecast_metrics(1)

    assert forecast["boosted_cycle_weeks"] == 4
    assert forecast["boosted_weeks_per_cycle"] == 1
    assert forecast["boosted_week_multiplier"] == 1.4


def test_seasonality_does_not_invent_consumption_when_no_measurements_exist():
    forecast = InventoryPlanningService._seasonal_forecast_metrics(0)

    assert forecast["normal_weekly_demand"] == 0
    assert forecast["boosted_weekly_demand"] == 0
    assert forecast["average_weekly_demand"] == 0
    assert forecast["monthly_forecast_demand"] == 0
