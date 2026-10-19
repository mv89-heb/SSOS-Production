from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import distinct, select

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_consumption_planning_service import InventoryConsumptionPlanningService
from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService


class InventoryCalendarService:
    """Calendar/period facade; replenishment calculations live in one canonical engine."""

    DEFAULT_COUNT_WEEKDAY = 6
    DEFAULT_COUNT_HOUR = 8
    DEFAULT_HOLIDAY_MULTIPLIER = 1.25

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.engine = InventoryConsumptionPlanningService(tenant_id)

    @staticmethod
    def _parse_weekdays(value):
        return InventoryUnifiedPlanningService._parse_weekdays(value)

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

    def schedule_for_product(self, product, today=None, periods=None, base_schedule=None):
        """Return the supplier schedule while preserving caller-provided schedule overrides."""
        today = today or datetime.now(timezone.utc).date()
        periods = periods if periods is not None else self.periods(
            start=today, end=today + timedelta(days=180), active_only=True
        )
        if base_schedule is None:
            base_schedule = self.engine._schedule(
                product,
                db.session.scalar(
                    select(Supplier).where(
                        Supplier.id == product.supplier_id,
                        Supplier.tenant_id == self.tenant_id,
                        Supplier.active.is_(True),
                    )
                ),
                today,
                periods,
            )
        base_order_days = set(base_schedule.get("order_days") or [])
        base_delivery_days = set(base_schedule.get("delivery_days") or [])

        def days_for(target, field, fallback):
            period = self._period_for_date(periods, target)
            raw = getattr(period, field, None) if period else None
            return self._parse_weekdays(raw) if raw else set() or fallback

        next_order = None
        for offset in range(181):
            candidate = today + timedelta(days=offset)
            if candidate.weekday() in (days_for(candidate, "order_days", base_order_days) or base_order_days):
                next_order = candidate
                break

        next_delivery = None
        if next_order:
            for offset in range(1, 181):
                candidate = next_order + timedelta(days=offset)
                if candidate.weekday() in (days_for(candidate, "delivery_days", base_delivery_days) or base_delivery_days):
                    next_delivery = candidate
                    break

        period_for_order = self._period_for_date(periods, next_order) if next_order else None
        return {
            **base_schedule,
            "next_order_date": next_order.isoformat() if next_order else None,
            "next_delivery_date": next_delivery.isoformat() if next_delivery else None,
            "recommended_check_date": next_order.isoformat() if next_order else None,
            "order_cutoff_time": (
                period_for_order.order_cutoff_time
                if period_for_order
                else base_schedule.get("order_cutoff_time")
            ),
            "schedule_adjusted_for_period": bool(
                (next_order and base_schedule.get("next_order_date") != next_order.isoformat())
                or (next_delivery and base_schedule.get("next_delivery_date") != next_delivery.isoformat())
            ),
        }

    def _consumption_metrics(self, product_id: int, lookback_days=60):
        since = datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
        metric = self.engine._consumption_batch([int(product_id)], since).get(int(product_id), {})
        return (
            Decimal(str(metric.get("consumption", 0))),
            Decimal(str(metric.get("observed_days", 0))),
            Decimal(str(metric.get("receipts", 0))),
            int(metric.get("stock_checks", 0)),
        )

    def _inbound_quantities(self, product_ids=None):
        if product_ids is None:
            product_ids = db.session.scalars(
                select(Product.id).where(Product.tenant_id == self.tenant_id, Product.active.is_(True))
            ).all()
        return self.engine._open_inbound([int(product_id) for product_id in product_ids])

    def recommendation(self, product_id: int, *, lookback_days=60, safety_days=2, inbound_quantities=None):
        row = self.engine.recommendation(
            product_id, lookback_days=lookback_days, safety_days=safety_days
        )
        if inbound_quantities is not None and row:
            inbound = Decimal(str(inbound_quantities.get(int(product_id), 0) or 0))
            current_stock = Decimal(str(row.get("current_stock", 0) or 0))
            target_stock = Decimal(str(
                row.get("holiday_adjusted_target_stock",
                        row.get("target_stock", row.get("reorder_point", 0))) or 0
            ))
            row["confirmed_inbound"] = float(inbound)
            row["recommended_order"] = float(max(Decimal("0"), target_stock - current_stock - inbound))
            if row.get("status") not in ("urgent", "insufficient_data"):
                row["status"] = "reorder" if current_stock + inbound <= target_stock else "healthy"
        return row

    def recommendations(self, *, lookback_days=60, safety_days=2, limit=500):
        return self.engine.recommendations(lookback_days=lookback_days, safety_days=safety_days, limit=limit)

    def count_status(self):
        today = datetime.now(timezone.utc).date()
        products = db.session.scalars(select(Product.id).where(Product.tenant_id == self.tenant_id, Product.active.is_(True))).all()
        product_count = len(products)
        window_start = today - timedelta(days=6)
        counted_ids = db.session.scalars(select(distinct(InventoryMovement.product_id)).where(InventoryMovement.tenant_id == self.tenant_id, InventoryMovement.movement_type == MOVEMENT_COUNT, InventoryMovement.occurred_at >= datetime.combine(window_start, datetime.min.time(), tzinfo=timezone.utc), InventoryMovement.product_id.in_(products or [-1]))).all()
        counted_products = len(counted_ids)
        completed = product_count > 0 and counted_products == product_count
        days_until_due = (self.DEFAULT_COUNT_WEEKDAY - today.weekday()) % 7
        if days_until_due == 0 and completed:
            days_until_due = 7
        next_due = today + timedelta(days=days_until_due)
        return {"count_weekday": self.DEFAULT_COUNT_WEEKDAY, "count_time": f"{self.DEFAULT_COUNT_HOUR:02d}:00", "active_products": product_count, "counted_products_last_7_days": counted_products, "completion_percent": round((counted_products / product_count) * 100, 1) if product_count else 0, "completed": completed, "due": not completed and today >= next_due, "next_due_date": next_due.isoformat(), "window_start": window_start.isoformat()}
