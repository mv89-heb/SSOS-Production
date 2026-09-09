from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from werkzeug.exceptions import NotFound

from app.extensions import db
from app.models.inventory_movement import (
    InventoryMovement,
    MOVEMENT_ADJUSTMENT,
    MOVEMENT_ISSUE,
    MOVEMENT_RECEIPT,
)
from app.models.product import Product


class InventoryPlanningService:
    """Maintain warehouse stock and turn real issue history into replenishment advice."""

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
        if movement_type not in (MOVEMENT_RECEIPT, MOVEMENT_ISSUE, MOVEMENT_ADJUSTMENT):
            raise ValueError("movement_type must be receipt, issue or adjustment")
        amount = self._decimal(quantity)
        if amount <= 0:
            raise ValueError("quantity must be greater than zero")

        product = self._product(int(product_id), lock=True)
        current = Decimal(str(product.current_stock or 0))
        delta = amount if movement_type == MOVEMENT_RECEIPT else -amount if movement_type == MOVEMENT_ISSUE else amount
        if movement_type == MOVEMENT_ADJUSTMENT:
            # Adjustment is an absolute correction, not a receipt/issue.
            new_balance = amount
        else:
            new_balance = current + delta
        if new_balance < 0:
            raise ValueError("movement would make stock negative")

        product.current_stock = int(new_balance) if new_balance == new_balance.to_integral_value() else float(new_balance)
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

    def recommendation(self, product_id: int, *, lookback_days=60, lead_time_days=7, safety_days=2):
        lookback_days = max(7, min(int(lookback_days), 365))
        lead_time_days = max(0, min(int(lead_time_days), 90))
        safety_days = max(0, min(int(safety_days), 90))
        product = self._product(int(product_id))
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=lookback_days)

        issue_total = db.session.scalar(
            select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id == product.id,
                InventoryMovement.movement_type == MOVEMENT_ISSUE,
                InventoryMovement.occurred_at >= since,
            )
        ) or 0
        receipt_total = db.session.scalar(
            select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id == product.id,
                InventoryMovement.movement_type == MOVEMENT_RECEIPT,
                InventoryMovement.occurred_at >= since,
            )
        ) or 0
        issue_total = Decimal(str(issue_total))
        receipt_total = Decimal(str(receipt_total))
        average_daily_usage = issue_total / Decimal(lookback_days)
        lead_time_demand = average_daily_usage * Decimal(lead_time_days)
        safety_stock = average_daily_usage * Decimal(safety_days)
        reorder_point = lead_time_demand + safety_stock
        current_stock = Decimal(str(product.current_stock or 0))
        recommended_order = max(Decimal("0"), reorder_point - current_stock)
        coverage_days = (current_stock / average_daily_usage) if average_daily_usage > 0 else None

        if issue_total == 0:
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
            "issues_in_period": float(issue_total),
            "receipts_in_period": float(receipt_total),
            "average_daily_usage": round(float(average_daily_usage), 3),
            "lead_time_days": lead_time_days,
            "lead_time_demand": round(float(lead_time_demand), 3),
            "safety_stock": round(float(safety_stock), 3),
            "reorder_point": round(float(reorder_point), 3),
            "recommended_order": round(float(recommended_order), 3),
            "coverage_days": round(float(coverage_days), 1) if coverage_days is not None else None,
            "status": status,
            "data_ready": issue_total > 0,
        }

    def recommendations(self, *, lookback_days=60, lead_time_days=7, safety_days=2, limit=100):
        products = db.session.scalars(
            select(Product).where(Product.tenant_id == self.tenant_id, Product.active.is_(True)).order_by(Product.name).limit(max(1, min(int(limit), 500)))
        ).all()
        rows = [self.recommendation(product.id, lookback_days=lookback_days, lead_time_days=lead_time_days, safety_days=safety_days) for product in products]
        priority = {"urgent": 0, "reorder": 1, "healthy": 2, "insufficient_data": 3}
        rows.sort(key=lambda row: (priority[row["status"]], -(row["recommended_order"] or 0), row["product_name"]))
        return rows
