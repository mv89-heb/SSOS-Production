from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, distinct

from app.extensions import db
from app.models.inventory_movement import InventoryMovement
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT
from app.models.product import Product
from app.services.inventory_planning_service import InventoryPlanningService


class InventoryCalendarService:
    """Adds calendar-aware demand and supplier scheduling on top of physical stock counts."""

    DEFAULT_COUNT_WEEKDAY = 6  # Sunday
    DEFAULT_COUNT_HOUR = 8
    DEFAULT_HOLIDAY_MULTIPLIER = 1.25

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.base = InventoryPlanningService(tenant_id)

    @staticmethod
    def _parse_weekdays(value):
        return InventoryPlanningService._parse_weekdays(value)

    def periods(self, *, start=None, end=None, active_only=False):
        statement = select(InventoryPlanningPeriod).where(InventoryPlanningPeriod.tenant_id == self.tenant_id)
        if active_only:
            statement = statement.where(InventoryPlanningPeriod.active.is_(True))
        if start:
            statement = statement.where(InventoryPlanningPeriod.end_date >= start)
        if end:
            statement = statement.where(InventoryPlanningPeriod.start_date <= end)
        return db.session.scalars(
            statement.order_by(InventoryPlanningPeriod.start_date.asc(), InventoryPlanningPeriod.id.asc())
        ).all()

    @staticmethod
    def _period_for_date(rows, target_date):
        matches = [row for row in rows if row.start_date <= target_date <= row.end_date]
        return matches[-1] if matches else None

    def period_for_date(self, target_date: date):
        return self._period_for_date(self.periods(start=target_date, end=target_date, active_only=True), target_date)

    def multiplier_for_date(self, target_date: date, periods=None):
        period = self._period_for_date(periods or [], target_date) if periods is not None else self.period_for_date(target_date)
        return Decimal(str(period.consumption_multiplier or 1)) if period else Decimal("1")

    def schedule_for_product(self, product, today=None, periods=None):
        today = today or datetime.now(timezone.utc).date()
        periods = periods if periods is not None else self.periods(start=today, end=today + timedelta(days=180), active_only=True)
        base_schedule = self.base._supplier_schedule(product)
        base_order_days = set(base_schedule.get("order_days") or [])
        base_delivery_days = set(base_schedule.get("delivery_days") or [])

        def days_for(target, field, fallback):
            period = self._period_for_date(periods, target)
            raw = getattr(period, field, None) if period else None
            parsed = self._parse_weekdays(raw) if raw else set()
            return parsed or fallback

        next_order = None
        for offset in range(181):
            candidate = today + timedelta(days=offset)
            if candidate.weekday() in days_for(candidate, "order_days", base_order_days):
                next_order = candidate
                break

        next_delivery = None
        if next_order:
            for offset in range(1, 181):
                candidate = next_order + timedelta(days=offset)
                if candidate.weekday() in days_for(candidate, "delivery_days", base_delivery_days):
                    next_delivery = candidate
                    break

        return {
            **base_schedule,
            "next_order_date": next_order.isoformat() if next_order else None,
            "next_delivery_date": next_delivery.isoformat() if next_delivery else None,
            "recommended_check_date": next_order.isoformat() if next_order else None,
            "schedule_adjusted_for_period": bool(
                (next_order and base_schedule.get("next_order_date") != next_order.isoformat())
                or (next_delivery and base_schedule.get("next_delivery_date") != next_delivery.isoformat())
            ),
        }

    def _forecast_demand(self, daily_rate: Decimal, start: date, end: date, periods):
        if end < start or daily_rate <= 0:
            return Decimal("0")
        total = Decimal("0")
        current = start
        while current <= end:
            total += daily_rate * self.multiplier_for_date(current, periods)
            current += timedelta(days=1)
        return total

    def _inbound_quantities(self):
        totals = {}
        orders = db.session.scalars(
            select(Order).where(
                Order.tenant_id == self.tenant_id,
                Order.status.in_((STATUS_APPROVED, STATUS_SENT)),
            )
        ).all()
        for order in orders:
            for item in order.items or []:
                try:
                    product_id = int(item.get("product_id"))
                    quantity = Decimal(str(item.get("quantity") or 0))
                except (AttributeError, TypeError, ValueError):
                    continue
                if quantity > 0:
                    totals[product_id] = totals.get(product_id, Decimal("0")) + quantity
        return totals

    def recommendation(self, product_id: int, *, lookback_days=60, safety_days=2, inbound_quantities=None):
        row = self.base.recommendation(product_id, lookback_days=lookback_days, safety_days=safety_days)
        product = db.session.scalar(
            select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
        )
        if product is None:
            return row

        today = datetime.now(timezone.utc).date()
        base_horizon = max(1, int(row.get("planning_horizon_days") or safety_days))
        window_end = today + timedelta(days=max(base_horizon, 180))
        periods = self.periods(start=today, end=window_end, active_only=True)
        schedule = self.schedule_for_product(product, today=today, periods=periods)
        delivery_date = date.fromisoformat(schedule["next_delivery_date"]) if schedule.get("next_delivery_date") else None
        daily_rate = Decimal(str(row.get("average_daily_usage") or 0))
        current_stock = Decimal(str(row.get("current_stock") or 0))
        inbound = (inbound_quantities or {}).get(product.id, Decimal("0"))

        if delivery_date and delivery_date >= today:
            target_end = delivery_date + timedelta(days=max(0, int(safety_days)))
        else:
            target_end = today + timedelta(days=base_horizon)
        target_end = min(target_end, window_end)

        holiday_adjusted_demand = self._forecast_demand(daily_rate, today, target_end, periods)
        target_stock = holiday_adjusted_demand
        recommended_order = max(Decimal("0"), target_stock - current_stock - inbound)
        active_periods = [p for p in periods if p.end_date >= today and p.start_date <= target_end]

        row.update({
            "current_stock": float(current_stock),
            "confirmed_inbound": float(inbound),
            "base_average_daily_usage": round(float(daily_rate), 3),
            "holiday_adjusted_demand": round(float(holiday_adjusted_demand), 3),
            "holiday_adjusted_target_stock": round(float(target_stock), 3),
            "recommended_order": round(float(recommended_order), 3),
            "planning_horizon_days": max(0, (target_end - today).days),
            "supplier_schedule": schedule,
            "active_planning_periods": [p.to_dict() for p in active_periods],
            "planning_notes": [
                "הכמות מבוססת על ספירות פיזיות ורכישות, ללא צורך בניפוקים ידניים.",
                "תקופות מיוחדות משנות את התחזית לפי מכפיל הצריכה שהוגדר.",
                "הזמנות פתוחות במצב מאושר/נשלח נלקחות כמלאי נכנס כאשר שורת ההזמנה כוללת product_id.",
            ],
        })
        if active_periods:
            row["status"] = "reorder" if recommended_order > 0 else row.get("status", "healthy")
        return row

    def recommendations(self, *, lookback_days=60, safety_days=2, limit=500):
        products = db.session.scalars(
            select(Product)
            .where(Product.tenant_id == self.tenant_id, Product.active.is_(True))
            .order_by(Product.name.asc())
            .limit(max(1, min(int(limit), 500)))
        ).all()
        inbound = self._inbound_quantities()
        rows = [
            self.recommendation(product.id, lookback_days=lookback_days, safety_days=safety_days, inbound_quantities=inbound)
            for product in products
        ]
        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(
            key=lambda row: (
                priority.get(row.get("status"), 4),
                -(row.get("recommended_order") or 0),
                row.get("product_name", ""),
            )
        )
        return rows

    def count_status(self):
        today = datetime.now(timezone.utc).date()
        products = db.session.scalars(
            select(Product.id).where(Product.tenant_id == self.tenant_id, Product.active.is_(True))
        ).all()
        product_count = len(products)
        window_start = today - timedelta(days=6)
        counted_ids = db.session.scalars(
            select(distinct(InventoryMovement.product_id)).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.movement_type == "count",
                InventoryMovement.occurred_at >= datetime.combine(window_start, datetime.min.time(), tzinfo=timezone.utc),
                InventoryMovement.product_id.in_(products or [-1]),
            )
        ).all()
        counted_products = len(counted_ids)
        completed = product_count > 0 and counted_products == product_count
        days_until_due = (self.DEFAULT_COUNT_WEEKDAY - today.weekday()) % 7
        if days_until_due == 0 and completed:
            days_until_due = 7
        next_due = today + timedelta(days=days_until_due)
        return {
            "count_weekday": self.DEFAULT_COUNT_WEEKDAY,
            "count_time": f"{self.DEFAULT_COUNT_HOUR:02d}:00",
            "active_products": product_count,
            "counted_products_last_7_days": counted_products,
            "completion_percent": round((counted_products / product_count) * 100, 1) if product_count else 0,
            "completed": completed,
            "due": not completed and today >= next_due,
            "next_due_date": next_due.isoformat(),
            "window_start": window_start.isoformat(),
        }
