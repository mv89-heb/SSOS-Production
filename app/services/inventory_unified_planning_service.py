from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import func, select

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT, MOVEMENT_RECEIPT
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.models.supplier import Supplier

_HEBREW_WEEKDAYS = {"ראשון": 6, "שני": 0, "שלישי": 1, "רביעי": 2, "חמישי": 3, "שישי": 4, "שבת": 5}
_ENGLISH_WEEKDAYS = {"sunday": 6, "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5}


class InventoryUnifiedPlanningService:
    """Single canonical replenishment engine for count-based inventory planning."""

    DEFAULT_HORIZON_DAYS = 180
    DEFAULT_HOLIDAY_MULTIPLIER = Decimal("1.25")

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _parse_weekdays(value):
        if not value:
            return set()
        tokens = [token.strip().lower() for token in re.split(r"[,;/|]+", str(value)) if token.strip()]
        result = set()
        for token in tokens:
            if token in _HEBREW_WEEKDAYS:
                result.add(_HEBREW_WEEKDAYS[token])
            elif token in _ENGLISH_WEEKDAYS:
                result.add(_ENGLISH_WEEKDAYS[token])
            elif token.isdigit() and 0 <= int(token) <= 6:
                result.add(int(token))
        return result

    @staticmethod
    def _period_for_date(periods, target):
        matches = [p for p in periods if p.start_date <= target <= p.end_date]
        return matches[-1] if matches else None

    def _periods(self, start, end):
        return db.session.scalars(
            select(InventoryPlanningPeriod).where(
                InventoryPlanningPeriod.tenant_id == self.tenant_id,
                InventoryPlanningPeriod.active.is_(True),
                InventoryPlanningPeriod.end_date >= start,
                InventoryPlanningPeriod.start_date <= end,
            ).order_by(InventoryPlanningPeriod.start_date.asc(), InventoryPlanningPeriod.id.asc())
        ).all()

    def _multiplier(self, target, periods):
        period = self._period_for_date(periods, target)
        return Decimal(str(period.consumption_multiplier or 1)) if period else Decimal("1")

    def _schedule(self, product, supplier, today, periods):
        if supplier is None:
            return {"supplier_id": product.supplier_id, "supplier_name": None, "order_days": [], "delivery_days": [], "next_order_date": None, "next_delivery_date": None, "order_cutoff_time": None, "schedule_ready": False}
        default_order = self._parse_weekdays(supplier.order_days)
        default_delivery = self._parse_weekdays(supplier.delivery_days)

        def days_for(target, field, fallback):
            period = self._period_for_date(periods, target)
            raw = getattr(period, field, None) if period else None
            return self._parse_weekdays(raw) or fallback

        next_order = None
        for offset in range(self.DEFAULT_HORIZON_DAYS + 1):
            candidate = today + timedelta(days=offset)
            if candidate.weekday() in days_for(candidate, "order_days", default_order):
                next_order = candidate
                break

        next_delivery = None
        if next_order:
            for offset in range(1, self.DEFAULT_HORIZON_DAYS + 1):
                candidate = next_order + timedelta(days=offset)
                if candidate.weekday() in days_for(candidate, "delivery_days", default_delivery):
                    next_delivery = candidate
                    break

        order_period = self._period_for_date(periods, next_order) if next_order else None
        return {
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "order_days": sorted(default_order),
            "delivery_days": sorted(default_delivery),
            "next_order_date": next_order.isoformat() if next_order else None,
            "next_delivery_date": next_delivery.isoformat() if next_delivery else None,
            "recommended_check_date": next_order.isoformat() if next_order else None,
            "order_cutoff_time": order_period.order_cutoff_time if order_period else None,
            "schedule_ready": bool(default_order and default_delivery),
        }

    def _consumption_batch(self, product_ids, since):
        if not product_ids:
            return {}
        counts = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id.in_(product_ids),
                InventoryMovement.movement_type == MOVEMENT_COUNT,
                InventoryMovement.occurred_at >= since,
            ).order_by(InventoryMovement.product_id.asc(), InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
        receipts = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id.in_(product_ids),
                InventoryMovement.movement_type == MOVEMENT_RECEIPT,
                InventoryMovement.occurred_at >= since,
            ).order_by(InventoryMovement.product_id.asc(), InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
        counts_by = {}
        receipts_by = {}
        for row in counts:
            counts_by.setdefault(row.product_id, []).append(row)
        for row in receipts:
            receipts_by.setdefault(row.product_id, []).append(row)

        result = {}
        for product_id in product_ids:
            rows = counts_by.get(product_id, [])
            incoming = receipts_by.get(product_id, [])
            consumption = Decimal("0")
            observed_days = Decimal("0")
            total_receipts = Decimal("0")
            receipt_index = 0
            for previous, current in zip(rows, rows[1:]):
                while receipt_index < len(incoming) and incoming[receipt_index].occurred_at <= previous.occurred_at:
                    receipt_index += 1
                interval_received = Decimal("0")
                scan_index = receipt_index
                while scan_index < len(incoming) and incoming[scan_index].occurred_at <= current.occurred_at:
                    interval_received += Decimal(str(incoming[scan_index].quantity or 0))
                    scan_index += 1
                days = Decimal(str(max((current.occurred_at - previous.occurred_at).total_seconds() / 86400, 0)))
                if days <= 0:
                    continue
                previous_balance = Decimal(str(previous.balance_after or 0))
                current_balance = Decimal(str(current.balance_after or 0))
                interval_consumption = previous_balance + interval_received - current_balance
                if interval_consumption > 0:
                    consumption += interval_consumption
                observed_days += days
                total_receipts += interval_received
            result[product_id] = {
                "consumption": consumption,
                "observed_days": observed_days,
                "average_daily_usage": consumption / observed_days if observed_days > 0 else Decimal("0"),
                "receipts": total_receipts,
                "stock_checks": len(rows),
            }
        return result

    def _open_inbound(self, product_ids):
        if not product_ids:
            return {}
        ordered = dict(db.session.execute(
            select(OrderItem.product_id, func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.tenant_id == self.tenant_id,
                Order.tenant_id == self.tenant_id,
                OrderItem.product_id.in_(product_ids),
                Order.status.in_((STATUS_APPROVED, STATUS_SENT)),
            ).group_by(OrderItem.product_id)
        ).all())
        received = dict(db.session.execute(
            select(OrderItem.product_id, func.coalesce(func.sum(ReceiptItem.quantity), 0))
            .join(ReceiptItem, ReceiptItem.order_item_id == OrderItem.id)
            .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
            .where(
                OrderItem.tenant_id == self.tenant_id,
                ReceiptItem.tenant_id == self.tenant_id,
                Receipt.tenant_id == self.tenant_id,
                OrderItem.product_id.in_(product_ids),
                Receipt.status == RECEIPT_POSTED,
            ).group_by(OrderItem.product_id)
        ).all())
        return {
            product_id: max(Decimal("0"), Decimal(str(ordered.get(product_id, 0))) - Decimal(str(received.get(product_id, 0))))
            for product_id in product_ids
            if max(Decimal("0"), Decimal(str(ordered.get(product_id, 0))) - Decimal(str(received.get(product_id, 0)))) > 0
        }

    def _forecast(self, daily_rate, start, end, periods):
        if daily_rate <= 0 or end < start:
            return Decimal("0")
        total = Decimal("0")
        current = start
        while current <= end:
            total += daily_rate * self._multiplier(current, periods)
            current += timedelta(days=1)
        return total

    def recommendations(self, *, lookback_days=60, safety_days=2, limit=500):
        lookback_days = max(7, min(int(lookback_days), 365))
        safety_days = max(0, min(int(safety_days), 90))
        limit = max(1, min(int(limit), 500))
        products = db.session.scalars(
            select(Product).where(Product.tenant_id == self.tenant_id, Product.active.is_(True)).order_by(Product.name.asc()).limit(limit)
        ).all()
        if not products:
            return []

        today = datetime.now(timezone.utc).date()
        window_end = today + timedelta(days=self.DEFAULT_HORIZON_DAYS)
        periods = self._periods(today, window_end)
        supplier_ids = {p.supplier_id for p in products if p.supplier_id is not None}
        suppliers = {
            s.id: s for s in db.session.scalars(
                select(Supplier).where(
                    Supplier.tenant_id == self.tenant_id,
                    Supplier.id.in_(supplier_ids or [-1]),
                    Supplier.active.is_(True),
                )
            ).all()
        }
        product_ids = [p.id for p in products]
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        metrics = self._consumption_batch(product_ids, since)
        inbound = self._open_inbound(product_ids)

        rows = []
        for product in products:
            metric = metrics.get(product.id, {})
            daily_rate = metric.get("average_daily_usage", Decimal("0"))
            supplier = suppliers.get(product.supplier_id)
            schedule = self._schedule(product, supplier, today, periods)
            delivery_date = date.fromisoformat(schedule["next_delivery_date"]) if schedule.get("next_delivery_date") else None
            order_date = date.fromisoformat(schedule["next_order_date"]) if schedule.get("next_order_date") else None
            lead_time_days = max(0, (delivery_date - order_date).days) if delivery_date and order_date else 0
            days_until_order = (order_date - today).days if order_date else None
            horizon = lead_time_days + safety_days
            if days_until_order is not None:
                horizon = max(horizon, days_until_order + lead_time_days + safety_days)
            horizon = max(1, horizon)
            target_end = min(window_end, delivery_date + timedelta(days=safety_days) if delivery_date else today + timedelta(days=horizon))
            demand = self._forecast(daily_rate, today, target_end, periods)
            safety_stock = self._forecast(daily_rate, target_end + timedelta(days=1), target_end + timedelta(days=max(1, safety_days)), periods)
            target_stock = demand + safety_stock
            current_stock = Decimal(str(product.current_stock or 0))
            open_inbound = inbound.get(product.id, Decimal("0"))
            available = current_stock + open_inbound
            recommended = max(Decimal("0"), target_stock - available)
            coverage = current_stock / daily_rate if daily_rate > 0 else None
            checks = metric.get("stock_checks", 0)
            if checks < 2:
                status = "insufficient_data"
            elif current_stock <= 0:
                status = "urgent"
            elif available <= target_stock:
                status = "reorder"
            else:
                status = "healthy"
            rows.append({
                "product_id": product.id,
                "product_name": product.name,
                "current_stock": float(current_stock),
                "open_inbound": float(open_inbound),
                "confirmed_inbound": float(open_inbound),
                "available_for_planning": float(available),
                "reserved_quantity": 0.0,
                "average_daily_usage": round(float(daily_rate), 3),
                "base_average_daily_usage": round(float(daily_rate), 3),
                "estimated_depletion": round(float(metric.get("consumption", 0)), 3),
                "receipts_in_observation_period": round(float(metric.get("receipts", 0)), 3),
                "stock_checks_in_period": checks,
                "observed_days": round(float(metric.get("observed_days", 0)), 1),
                "lead_time_days": lead_time_days,
                "days_until_next_order": days_until_order,
                "planning_horizon_days": max(0, (target_end - today).days),
                "lead_time_demand": round(float(demand), 3),
                "holiday_adjusted_demand": round(float(demand), 3),
                "safety_stock": round(float(safety_stock), 3),
                "target_stock": round(float(target_stock), 3),
                "holiday_adjusted_target_stock": round(float(target_stock), 3),
                "reorder_point": round(float(target_stock), 3),
                "recommended_order": round(float(recommended), 3),
                "coverage_days": round(float(coverage), 1) if coverage is not None else None,
                "status": status,
                "data_ready": checks >= 2,
                "supplier_schedule": schedule,
                "active_planning_periods": [p.to_dict() for p in periods if p.end_date >= today and p.start_date <= target_end],
                "planning_engine": "unified-v1",
                "planning_notes": [
                    "הצריכה מבוססת על ספירות פיזיות; אין צורך לרשום כל ניפוק.",
                    "תחזית הביקוש מתאימה מכפילי תקופות מיוחדות לימים העתידיים בלבד.",
                    "מלאי נכנס = הזמנה מאושרת/נשלחה פחות קליטות בפועל.",
                    "כמות שכבר נמצאת בהזמנה פתוחה נלקחת בחשבון כדי למנוע הזמנה כפולה.",
                ],
            })

        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(key=lambda row: (priority.get(row["status"], 4), -row["recommended_order"], row["product_name"]))
        return rows

    def recommendation(self, product_id: int, **kwargs):
        rows = self.recommendations(**kwargs)
        for row in rows:
            if row["product_id"] == int(product_id):
                return row
        return None
