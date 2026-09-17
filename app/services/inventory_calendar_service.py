from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import distinct, select

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService


class InventoryCalendarService:
    """Calendar/period facade; replenishment calculations live in one canonical engine."""

    DEFAULT_COUNT_WEEKDAY = 6
    DEFAULT_COUNT_HOUR = 8
    DEFAULT_HOLIDAY_MULTIPLIER = 1.25

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.engine = InventoryUnifiedPlanningService(tenant_id)

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

    def schedule_for_product(self, product, today=None, periods=None):
        today = today or datetime.now(timezone.utc).date()
        periods = periods if periods is not None else self.periods(start=today, end=today + timedelta(days=180), active_only=True)
        supplier = db.session.scalar(select(Supplier).where(Supplier.id == product.supplier_id, Supplier.tenant_id == self.tenant_id, Supplier.active.is_(True)))
        return self.engine._schedule(product, supplier, today, periods)

    def recommendation(self, product_id: int, *, lookback_days=60, safety_days=2, inbound_quantities=None):
        return self.engine.recommendation(product_id, lookback_days=lookback_days, safety_days=safety_days)

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
