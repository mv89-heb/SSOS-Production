from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import func, select
from werkzeug.exceptions import NotFound

from app.extensions import db
from app.models.inventory_movement import (
    InventoryMovement,
    MOVEMENT_ADJUSTMENT,
    MOVEMENT_COUNT,
    MOVEMENT_ISSUE,
    MOVEMENT_RECEIPT,
)
from app.models.product import Product
from app.models.supplier import Supplier


_HEBREW_WEEKDAYS = {
    "ראשון": 6,
    "שני": 0,
    "שלישי": 1,
    "רביעי": 2,
    "חמישי": 3,
    "שישי": 4,
    "שבת": 5,
}
_ENGLISH_WEEKDAYS = {
    "sunday": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
}


class InventoryPlanningService:
    """Use physical stock checks as the source of truth and estimate depletion between checks."""

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _decimal(value, field="quantity"):
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"{field} must be a number")
        if not result.is_finite():
            raise ValueError(f"{field} must be finite")
        return result

    @staticmethod
    def _parse_weekdays(value):
        if not value:
            return set()
        tokens = [token.strip().lower() for token in re.split(r"[,;/|]+", str(value)) if token.strip()]
        weekdays = set()
        for token in tokens:
            if token in _HEBREW_WEEKDAYS:
                weekdays.add(_HEBREW_WEEKDAYS[token])
            elif token in _ENGLISH_WEEKDAYS:
                weekdays.add(_ENGLISH_WEEKDAYS[token])
            elif token.isdigit() and 0 <= int(token) <= 6:
                weekdays.add(int(token))
        return weekdays

    @staticmethod
    def _next_weekday(start: date, weekdays):
        if not weekdays:
            return None
        for offset in range(8):
            candidate = start + timedelta(days=offset)
            if candidate.weekday() in weekdays:
                return candidate
        return None

    def _supplier_schedule(self, product):
        supplier = db.session.scalar(
            select(Supplier).where(
                Supplier.id == product.supplier_id,
                Supplier.tenant_id == self.tenant_id,
                Supplier.active.is_(True),
            )
        )
        if supplier is None:
            return {
                "supplier_id": product.supplier_id,
                "supplier_name": None,
                "order_days": [],
                "delivery_days": [],
                "next_order_date": None,
                "next_delivery_date": None,
                "recommended_check_date": None,
                "schedule_ready": False,
            }

        order_weekdays = self._parse_weekdays(supplier.order_days)
        delivery_weekdays = self._parse_weekdays(supplier.delivery_days)
        today = datetime.now(timezone.utc).date()
        next_order = self._next_weekday(today, order_weekdays)
        next_delivery = self._next_weekday(next_order or today, delivery_weekdays)
        if next_order and next_delivery and next_delivery < next_order:
            next_delivery = self._next_weekday(next_order + timedelta(days=1), delivery_weekdays)

        # The current schema stores ordering days but no cutoff hour. Do not invent one.
        return {
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "order_days": sorted(order_weekdays),
            "delivery_days": sorted(delivery_weekdays),
            "next_order_date": next_order.isoformat() if next_order else None,
            "next_delivery_date": next_delivery.isoformat() if next_delivery else None,
            "recommended_check_date": next_order.isoformat() if next_order else None,
            "order_cutoff_time": None,
            "schedule_ready": bool(order_weekdays and delivery_weekdays),
        }

    def _product(self, product_id: int, lock=False):
        statement = select(Product).where(Product.id == product_id, Product.tenant_id == self.tenant_id)
        if lock:
            statement = statement.with_for_update()
        product = db.session.scalar(statement)
        if product is None:
            raise NotFound("Product not found")
        return product

    def record_movement(self, *, product_id, movement_type, quantity, user_id=None,
                        reference_type=None, reference_id=None, note=None, occurred_at=None):
        if movement_type not in (MOVEMENT_RECEIPT, MOVEMENT_ISSUE, MOVEMENT_ADJUSTMENT, MOVEMENT_COUNT):
            raise ValueError("movement_type must be receipt, issue, adjustment or count")
        amount = self._decimal(quantity)
        if amount <= 0:
            raise ValueError("quantity must be greater than zero")
        if amount != amount.to_integral_value():
            raise ValueError("stock quantity must be a whole number")
        amount = amount.to_integral_value()

        product = self._product(int(product_id), lock=True)
        current = Decimal(str(product.current_stock or 0))
        if movement_type in (MOVEMENT_ADJUSTMENT, MOVEMENT_COUNT):
            # A physical count is an absolute observed balance, not a delta.
            new_balance = amount
        else:
            delta = amount if movement_type == MOVEMENT_RECEIPT else -amount
            new_balance = current + delta
        if new_balance < 0:
            raise ValueError("movement would make stock negative")

        product.current_stock = int(new_balance)
        movement = InventoryMovement(
            tenant_id=self.tenant_id,
            product_id=product.id,
            user_id=user_id,
            movement_type=movement_type,
            quantity=amount,
            balance_after=new_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )
        db.session.add(movement)
        db.session.flush()
        return movement

    def recommendation(self, product_id: int, *, lookback_days=60, lead_time_days=None, safety_days=2):
        lookback_days = max(7, min(int(lookback_days), 365))
        safety_days = max(0, min(int(safety_days), 90))
        product = self._product(int(product_id))
        schedule = self._supplier_schedule(product)

        now = datetime.now(timezone.utc)
        since = now - timedelta(days=lookback_days)
        counts = db.session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id == product.id,
                InventoryMovement.movement_type == MOVEMENT_COUNT,
                InventoryMovement.occurred_at >= since,
            )
            .order_by(InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()

        estimated_depletion = Decimal("0")
        observed_days = Decimal("0")
        if len(counts) >= 2:
            for previous, current in zip(counts, counts[1:]):
                previous_balance = Decimal(str(previous.balance_after or 0))
                current_balance = Decimal(str(current.balance_after or 0))
                days = Decimal(str(max((current.occurred_at - previous.occurred_at).total_seconds() / 86400, 0)))
                if days <= 0:
                    continue
                observed_days += days
                decrease = previous_balance - current_balance
                if decrease > 0:
                    estimated_depletion += decrease

        average_daily_usage = (estimated_depletion / observed_days) if observed_days > 0 else Decimal("0")

        next_order_date = date.fromisoformat(schedule["next_order_date"]) if schedule["next_order_date"] else None
        today = now.date()
        days_until_order = (next_order_date - today).days if next_order_date else None
        if lead_time_days is None:
            if schedule["next_delivery_date"] and next_order_date:
                next_delivery = date.fromisoformat(schedule["next_delivery_date"])
                lead_time_days = max(0, (next_delivery - next_order_date).days)
            else:
                lead_time_days = 0
        lead_time_days = max(0, min(int(lead_time_days), 90))

        horizon_days = lead_time_days + safety_days
        # If an order window exists, the stock check must cover the wait until that window.
        if days_until_order is not None:
            horizon_days = max(horizon_days, days_until_order + lead_time_days + safety_days)

        lead_time_demand = average_daily_usage * Decimal(horizon_days)
        safety_stock = average_daily_usage * Decimal(safety_days)
        reorder_point = lead_time_demand
        current_stock = Decimal(str(product.current_stock or 0))
        recommended_order = max(Decimal("0"), reorder_point - current_stock)
        coverage_days = (current_stock / average_daily_usage) if average_daily_usage > 0 else None

        if len(counts) < 2:
            status = "insufficient_data"
        elif current_stock <= 0:
            status = "urgent"
        elif current_stock <= reorder_point:
            status = "reorder"
        else:
            status = "healthy"

        return {
            "product_id": product.id,
            "product_name": product.name,
            "current_stock": float(current_stock),
            "lookback_days": lookback_days,
            "stock_checks_in_period": len(counts),
            "observed_days": round(float(observed_days), 1),
            "estimated_depletion": float(estimated_depletion),
            "average_daily_usage": round(float(average_daily_usage), 3),
            "lead_time_days": lead_time_days,
            "days_until_next_order": days_until_order,
            "planning_horizon_days": horizon_days,
            "lead_time_demand": round(float(lead_time_demand), 3),
            "safety_stock": round(float(safety_stock), 3),
            "reorder_point": round(float(reorder_point), 3),
            "recommended_order": round(float(recommended_order), 3),
            "coverage_days": round(float(coverage_days), 1) if coverage_days is not None else None,
            "status": status,
            "data_ready": len(counts) >= 2,
            "supplier_schedule": schedule,
        }

    def recommendations(self, *, lookback_days=60, lead_time_days=None, safety_days=2, limit=100):
        products = db.session.scalars(
            select(Product).where(
                Product.tenant_id == self.tenant_id,
                Product.active.is_(True),
            ).order_by(Product.name).limit(max(1, min(int(limit), 500)))
        ).all()
        rows = [
            self.recommendation(
                product.id,
                lookback_days=lookback_days,
                lead_time_days=lead_time_days,
                safety_days=safety_days,
            )
            for product in products
        ]
        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(key=lambda row: (priority[row["status"]], -(row["recommended_order"] or 0), row["product_name"]))
        return rows
