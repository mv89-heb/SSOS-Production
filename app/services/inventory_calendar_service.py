from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import distinct, select

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT, MOVEMENT_RECEIPT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT
from app.models.product import Product
from app.models.supplier import Supplier
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

    def schedule_for_product(self, product, today=None, periods=None, base_schedule=None):
        today = today or datetime.now(timezone.utc).date()
        periods = periods if periods is not None else self.periods(start=today, end=today + timedelta(days=180), active_only=True)
        base_schedule = base_schedule if base_schedule is not None else self.base._supplier_schedule(product)
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
        since = datetime.now(timezone.utc) - timedelta(days=max(7, min(int(lookback_days), 365)))
        from app.services.inventory_consumption_planning_service import InventoryConsumptionPlanningService

        metric = InventoryConsumptionPlanningService(self.tenant_id)._consumption_batch(
            [int(product_id)], since
        ).get(int(product_id), {})
        return (
            Decimal(str(metric.get("consumption", 0))),
            Decimal(str(metric.get("observed_days", 0))),
            Decimal(str(metric.get("receipts", 0))),
            int(metric.get("stock_checks", 0)),
        )

    def _inbound_quantities(self, product_ids=None):
        """Return outstanding inbound quantities from relational order lines and posted receipts."""
        from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService

        if product_ids is None:
            product_ids = db.session.scalars(
                select(Product.id).where(
                    Product.tenant_id == self.tenant_id,
                    Product.active.is_(True),
                )
            ).all()
        return InventoryUnifiedPlanningService(self.tenant_id)._open_inbound(
            [int(product_id) for product_id in product_ids]
        )

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
        configured_targets = [
            Decimal(str(value))
            for value in (product.recommended_stock, product.min_stock)
            if value is not None and Decimal(str(value)) > 0
        ]
        configured_target = max(configured_targets, default=Decimal("0"))
        # Never hide a zero-stock product just because its count history is incomplete.
        # When history is insufficient, use only an explicitly configured stock target;
        # do not fabricate consumption from missing observations.
        if stock_checks < 2 and (current_stock <= 0 or (
            product.min_stock is not None and current_stock <= Decimal(str(product.min_stock))
        )):
            target_stock = max(target_stock, configured_target)
        recommended_order = max(Decimal("0"), target_stock - current_stock - inbound)
        coverage_days = current_stock / daily_rate if daily_rate > 0 else None
        days_until_order = (date.fromisoformat(schedule["next_order_date"]) - today).days if schedule.get("next_order_date") else None
        active_periods = [p for p in periods if p.end_date >= today and p.start_date <= target_end]

        if current_stock <= 0:
            status = "urgent"
        elif stock_checks < 2 and product.min_stock is not None and current_stock <= Decimal(str(product.min_stock)):
            status = "reorder"
        elif stock_checks < 2:
            status = "insufficient_data"
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
        row.update(self.base._carton_metrics(
            product, current_stock, estimated_consumption, daily_rate, target_stock, recommended_order
        ))
        return row

    def recommendations(self, *, lookback_days=60, safety_days=2, limit=2000):
        """Calculate all product recommendations with bulk database reads."""
        lookback_days = max(7, min(int(lookback_days), 365))
        safety_days = max(0, min(int(safety_days), 90))
        products = db.session.scalars(
            select(Product).where(Product.tenant_id == self.tenant_id, Product.active.is_(True))
            .order_by(Product.name.asc()).limit(max(1, min(int(limit), 2000)))
        ).all()
        if not products:
            return []
        ids = [p.id for p in products]
        today = datetime.now(timezone.utc).date()
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        count_rows = db.session.scalars(
            select(InventoryMovement).where(InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id.in_(ids), InventoryMovement.movement_type == MOVEMENT_COUNT,
                InventoryMovement.occurred_at >= since)
            .order_by(InventoryMovement.product_id, InventoryMovement.occurred_at, InventoryMovement.id)
        ).all()
        counts_by_product = {}
        for m in count_rows:
            counts_by_product.setdefault(m.product_id, []).append(m)
        supplier_ids = {p.supplier_id for p in products if p.supplier_id is not None}
        suppliers = {}
        if supplier_ids:
            suppliers = {s.id: s for s in db.session.scalars(select(Supplier).where(
                Supplier.tenant_id == self.tenant_id, Supplier.id.in_(supplier_ids), Supplier.active.is_(True)
            )).all()}
        inbound = self._inbound_quantities()
        periods = self.periods(start=today, end=today + timedelta(days=180), active_only=True)
        from app.services.inventory_consumption_planning_service import InventoryConsumptionPlanningService
        consumption_metrics = InventoryConsumptionPlanningService(self.tenant_id)._consumption_batch(ids, since)
        rows = []
        for product in products:
            daily = {}
            for m in counts_by_product.get(product.id, []):
                key = m.occurred_at.date()
                if key not in daily or (m.occurred_at, m.id) > (daily[key].occurred_at, daily[key].id):
                    daily[key] = m
            counts = sorted(daily.values(), key=lambda m: (m.occurred_at, m.id))
            supplier = suppliers.get(product.supplier_id)
            base_schedule = self.base._supplier_schedule_from_supplier(product, supplier)
            row = self.base._recommendation_from_product(product, base_schedule, counts,
                lookback_days=lookback_days, safety_days=safety_days)
            metric = consumption_metrics.get(product.id, {})
            used = Decimal(str(metric.get("consumption", 0)))
            elapsed = Decimal(str(metric.get("observed_days", 0)))
            received_total = Decimal(str(metric.get("receipts", 0)))
            adjustment_delta = Decimal(str(metric.get("adjustment_delta", 0)))
            rate = used / elapsed if elapsed > 0 else Decimal("0")
            schedule = self.schedule_for_product(product, today=today, periods=periods, base_schedule=base_schedule)
            delivery = date.fromisoformat(schedule["next_delivery_date"]) if schedule.get("next_delivery_date") else None
            horizon = max(1, (delivery - today).days + safety_days) if delivery and delivery >= today else max(1, safety_days)
            horizon_end = min(today + timedelta(days=horizon), today + timedelta(days=180))
            demand = self._forecast_demand(rate, today, horizon_end, periods)
            safety = rate * Decimal(safety_days)
            stock = Decimal(str(product.current_stock or 0))
            inbound_qty = inbound.get(product.id, Decimal("0"))
            target = demand + safety
            configured_targets = [
                Decimal(str(value))
                for value in (product.recommended_stock, product.min_stock)
                if value is not None and Decimal(str(value)) > 0
            ]
            configured_target = max(configured_targets, default=Decimal("0"))
            if len(counts) < 2 and (stock <= 0 or (
                product.min_stock is not None and stock <= Decimal(str(product.min_stock))
            )):
                target = max(target, configured_target)
            recommended = max(Decimal("0"), target - stock - inbound_qty)
            coverage = stock / rate if rate > 0 else None
            if stock <= 0:
                status = "urgent"
            elif len(counts) < 2 and product.min_stock is not None and stock <= Decimal(str(product.min_stock)):
                status = "reorder"
            elif len(counts) < 2:
                status = "insufficient_data"
            else:
                status = "reorder" if stock <= target else "healthy"
            row.update({
                "current_stock": float(stock), "stock_checks_in_period": len(counts),
                "observed_days": round(float(elapsed), 1), "estimated_depletion": round(float(used), 3),
                "average_daily_usage": round(float(rate), 3), "base_average_daily_usage": round(float(rate), 3),
                "receipts_in_observation_period": round(float(received_total), 3),
                "adjustment_delta_in_observation_period": round(float(adjustment_delta), 3),
                "confirmed_inbound": float(inbound_qty), "holiday_adjusted_demand": round(float(demand), 3),
                "holiday_adjusted_target_stock": round(float(target), 3), "safety_stock": round(float(safety), 3),
                "reorder_point": round(float(target), 3), "recommended_order": round(float(recommended), 3),
                "coverage_days": round(float(coverage), 1) if coverage is not None else None,
                "planning_horizon_days": horizon, "status": status, "data_ready": len(counts) >= 2,
                "supplier_schedule": schedule, "active_planning_periods": [p.to_dict() for p in periods if p.end_date >= today and p.start_date <= horizon_end],
                "planning_notes": ["הצריכה מחושבת מספירות פיזיות ורכישות בין הספירות.", "ספירות חוזרות באותו יום מאוחדות ונשמרת האחרונה.", "התחזית מתחשבת בתקופות תכנון פעילות ובמלאי נכנס מאושר או שנשלח."]
            })
            row.update(self.base._carton_metrics(product, stock, used, rate, target, recommended))
            rows.append(row)
        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(key=lambda r: (priority.get(r.get("status"), 4), -(r.get("recommended_order") or 0), r.get("product_name", "")))
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
        # A weekly count is complete only when every active product has a physical
        # count in the rolling seven-day window. Once the Sunday deadline passes,
        # keep the requirement active on every subsequent day until completion.
        completed = product_count == 0 or counted_products == product_count
        days_until_due = (self.DEFAULT_COUNT_WEEKDAY - today.weekday()) % 7
        upcoming_due = today + timedelta(days=days_until_due)
        if completed:
            next_due = upcoming_due + (timedelta(days=7) if upcoming_due == today else timedelta(days=0))
            due = False
        else:
            days_since_deadline = (today.weekday() - self.DEFAULT_COUNT_WEEKDAY) % 7
            last_deadline = today - timedelta(days=days_since_deadline)
            next_due = last_deadline
            due = True
        return {
            "count_weekday": self.DEFAULT_COUNT_WEEKDAY,
            "count_time": f"{self.DEFAULT_COUNT_HOUR:02d}:00",
            "active_products": product_count,
            "counted_products_last_7_days": counted_products,
            "completion_percent": round((counted_products / product_count) * 100, 1) if product_count else 0,
            "completed": completed,
            "due": due,
            "next_due_date": next_due.isoformat(),
            "window_start": window_start.isoformat(),
        }
