from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import distinct, select

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT, MOVEMENT_RECEIPT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT
from app.models.product import Product
from app.services.inventory_planning_service import InventoryPlanningService


class InventoryCalendarService:
    """Physical-count source of truth with receipt-aware and holiday-aware replenishment planning."""

    DEFAULT_COUNT_WEEKDAY = 6
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
        return db.session.scalars(statement.order_by(InventoryPlanningPeriod.start_date.asc(), InventoryPlanningPeriod.id.asc())).all()

    @staticmethod
    def _period_for_date(rows, target_date):
        matches = [row for row in rows if row.start_date <= target_date <= row.end_date]
        return matches[-1] if matches else None

    def multiplier_for_date(self, target_date: date, periods=None):
        rows = periods if periods is not None else self.periods(start=target_date, end=target_date, active_only=True)
        period = self._period_for_date(rows, target_date)
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

        period_for_order = self._period_for_date(periods, next_order) if next_order else None
        return {
            **base_schedule,
            "next_order_date": next_order.isoformat() if next_order else None,
            "next_delivery_date": next_delivery.isoformat() if next_delivery else None,
            "recommended_check_date": next_order.isoformat() if next_order else None,
            "order_cutoff_time": period_for_order.order_cutoff_time if period_for_order else base_schedule.get("order_cutoff_time"),
            "schedule_adjusted_for_period": bool(
                (next_order and base_schedule.get("next_order_date") != next_order.isoformat())
                or (next_delivery and base_schedule.get("next_delivery_date") != next_delivery.isoformat())
            ),
        }

    def _consumption_metrics(self, product_id: int, lookback_days=60):
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=max(7, min(int(lookback_days), 365)))
        counts = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id == product_id,
                InventoryMovement.movement_type == MOVEMENT_COUNT,
                InventoryMovement.occurred_at >= since,
            ).order_by(InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
        if len(counts) < 2:
            return Decimal("0"), Decimal("0"), Decimal("0"), len(counts)

        receipts = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id == product_id,
                InventoryMovement.movement_type == MOVEMENT_RECEIPT,
                InventoryMovement.occurred_at >= since,
            ).order_by(InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
        estimated_consumption = Decimal("0")
        observed_days = Decimal("0")
        total_receipts = Decimal("0")
        for previous, current in zip(counts, counts[1:]):
            days = Decimal(str(max((current.occurred_at - previous.occurred_at).total_seconds() / 86400, 0)))
            if days <= 0:
                continue
            received = sum(
                (Decimal(str(item.quantity or 0)) for item in receipts if previous.occurred_at < item.occurred_at <= current.occurred_at),
                Decimal("0"),
            )
            previous_balance = Decimal(str(previous.balance_after or 0))
            current_balance = Decimal(str(current.balance_after or 0))
            consumption = previous_balance + received - current_balance
            if consumption > 0:
                estimated_consumption += consumption
            observed_days += days
            total_receipts += received
        return estimated_consumption, observed_days, total_receipts, len(counts)

    def _inbound_quantities(self):
        totals = {}
        orders = db.session.scalars(
            select(Order).where(Order.tenant_id == self.tenant_id, Order.status.in_((STATUS_APPROVED, STATUS_SENT)))
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

    def _forecast_demand(self, daily_rate: Decimal, start: date, end: date, periods):
        if end < start or daily_rate <= 0:
            return Decimal("0")
        total = Decimal("0")
        current = start
        while current <= end:
            total += daily_rate * self.multiplier_for_date(current, periods)
            current += timedelta(days=1)
        return total

    def recommendation(self, product_id: int, *, lookback_days=60, safety_days=2, inbound_quantities=None):
        row = self.base.recommendation(product_id, lookback_days=lookback_days, safety_days=safety_days)
        product = db.session.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id))
        if product is None:
            return row

        estimated_consumption, observed_days, total_receipts, stock_checks = self._consumption_metrics(product.id, lookback_days)
        daily_rate = estimated_consumption / observed_days if observed_days > 0 else Decimal("0")
        today = datetime.now(timezone.utc).date()
        base_horizon = max(1, int(row.get("planning_horizon_days") or safety_days))
        window_end = today + timedelta(days=max(base_horizon, 180))
        periods = self.periods(start=today, end=window_end, active_only=True)
        schedule = self.schedule_for_product(product, today=today, periods=periods)
        delivery_date = date.fromisoformat(schedule["next_delivery_date"]) if schedule.get("next_delivery_date") else None
        current_stock = Decimal(str(product.current_stock or 0))
        inbound = (inbound_quantities or {}).get(product.id, Decimal("0"))

        if delivery_date and delivery_date >= today:
            target_end = delivery_date + timedelta(days=max(0, int(safety_days)))
        else:
            target_end = today + timedelta(days=base_horizon)
        target_end = min(target_end, window_end)
        holiday_adjusted_demand = self._forecast_demand(daily_rate, today, target_end, periods)
        safety_stock = self._forecast_demand(daily_rate, target_end + timedelta(days=1), target_end + timedelta(days=max(1, int(safety_days))), periods)
        target_stock = holiday_adjusted_demand + safety_stock
        recommended_order = max(Decimal("0"), target_stock - current_stock - inbound)
        coverage_days = current_stock / daily_rate if daily_rate > 0 else None
        days_until_order = (date.fromisoformat(schedule["next_order_date"]) - today).days if schedule.get("next_order_date") else None
        active_periods = [p for p in periods if p.end_date >= today and p.start_date <= target_end]

        if stock_checks < 2:
            status = "insufficient_data"
        elif current_stock <= 0:
            status = "urgent"
        elif current_stock <= target_stock:
            status = "reorder"
        else:
            status = "healthy"

        row.update({
            "current_stock": float(current_stock),
            "stock_checks_in_period": stock_checks,
            "observed_days": round(float(observed_days), 1),
            "estimated_depletion": round(float(estimated_consumption), 3),
            "average_daily_usage": round(float(daily_rate), 3),
            "base_average_daily_usage": round(float(daily_rate), 3),
            "receipts_in_observation_period": round(float(total_receipts), 3),
            "confirmed_inbound": float(inbound),
            "holiday_adjusted_demand": round(float(holiday_adjusted_demand), 3),
            "holiday_adjusted_target_stock": round(float(target_stock), 3),
            "safety_stock": round(float(safety_stock), 3),
            "reorder_point": round(float(target_stock), 3),
            "recommended_order": round(float(recommended_order), 3),
            "coverage_days": round(float(coverage_days), 1) if coverage_days is not None else None,
            "days_until_next_order": days_until_order,
            "planning_horizon_days": max(0, (target_end - today).days),
            "status": status,
            "data_ready": stock_checks >= 2,
            "supplier_schedule": schedule,
            "active_planning_periods": [p.to_dict() for p in active_periods],
            "planning_notes": [
                "הצריכה מחושבת מנקודות ספירה פיזיות: מלאי פתיחה + רכישות בין הספירות - מלאי סיום.",
                "אין צורך לדווח על ניפוקים; לקיחות לא מדווחות מתגלמות בירידה בין הספירות.",
                "תקופות מיוחדות משנות את התחזית לפי מכפיל הצריכה שהוגדר.",
                "הזמנות פתוחות במצב מאושר/נשלח נלקחות כמלאי נכנס כאשר שורת ההזמנה כוללת product_id.",
            ],
        })
        return row

    def recommendations(self, *, lookback_days=60, safety_days=2, limit=500):
        products = db.session.scalars(
            select(Product).where(Product.tenant_id == self.tenant_id, Product.active.is_(True)).order_by(Product.name.asc()).limit(max(1, min(int(limit), 500)))
        ).all()
        inbound = self._inbound_quantities()
        rows = [self.recommendation(product.id, lookback_days=lookback_days, safety_days=safety_days, inbound_quantities=inbound) for product in products]
        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(key=lambda row: (priority.get(row.get("status"), 4), -(row.get("recommended_order") or 0), row.get("product_name", "")))
        return rows

    def count_status(self):
        today = datetime.now(timezone.utc).date()
        products = db.session.scalars(select(Product.id).where(Product.tenant_id == self.tenant_id, Product.active.is_(True))).all()
        product_count = len(products)
        window_start = today - timedelta(days=6)
        counted_ids = db.session.scalars(
            select(distinct(InventoryMovement.product_id)).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.movement_type == MOVEMENT_COUNT,
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
