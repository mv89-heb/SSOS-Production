from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.inventory_movement import (
    InventoryMovement,
    MOVEMENT_ADJUSTMENT,
    MOVEMENT_COUNT,
    MOVEMENT_RECEIPT,
)
from app.services.inventory_unified_planning_service import InventoryUnifiedPlanningService


class InventoryConsumptionPlanningService(InventoryUnifiedPlanningService):
    """Canonical planning engine with explicit adjustment-vs-consumption semantics."""

    def _consumption_batch(self, product_ids, since):
        if not product_ids:
            return {}

        movements = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == self.tenant_id,
                InventoryMovement.product_id.in_(product_ids),
                InventoryMovement.movement_type.in_((MOVEMENT_COUNT, MOVEMENT_RECEIPT, MOVEMENT_ADJUSTMENT)),
                InventoryMovement.occurred_at >= since,
            ).order_by(
                InventoryMovement.product_id.asc(),
                InventoryMovement.occurred_at.asc(),
                InventoryMovement.id.asc(),
            )
        ).all()

        events_by_product = {}
        for event in movements:
            events_by_product.setdefault(event.product_id, []).append(event)

        result = {}
        for product_id in product_ids:
            events = events_by_product.get(product_id, [])
            counts = [event for event in events if event.movement_type == MOVEMENT_COUNT]
            consumption = Decimal("0")
            observed_days = Decimal("0")
            total_receipts = Decimal("0")
            total_adjustment_delta = Decimal("0")

            for previous, current in zip(counts, counts[1:]):
                days = Decimal(str(max(
                    (current.occurred_at - previous.occurred_at).total_seconds() / 86400,
                    0,
                )))
                if days <= 0:
                    continue

                previous_balance = Decimal(str(previous.balance_after or 0))
                running_balance = previous_balance
                interval_received = Decimal("0")
                interval_adjustment_delta = Decimal("0")

                for event in events:
                    if event.occurred_at <= previous.occurred_at:
                        continue
                    if event.occurred_at > current.occurred_at:
                        break

                    if event.movement_type == MOVEMENT_RECEIPT:
                        quantity = Decimal(str(event.quantity or 0))
                        interval_received += quantity
                        running_balance += quantity
                    elif event.movement_type == MOVEMENT_ADJUSTMENT:
                        adjusted_balance = Decimal(str(event.balance_after or 0))
                        interval_adjustment_delta += adjusted_balance - running_balance
                        running_balance = adjusted_balance

                current_balance = Decimal(str(current.balance_after or 0))
                interval_consumption = (
                    previous_balance
                    + interval_received
                    + interval_adjustment_delta
                    - current_balance
                )
                if interval_consumption > 0:
                    consumption += interval_consumption

                observed_days += days
                total_receipts += interval_received
                total_adjustment_delta += interval_adjustment_delta

            result[product_id] = {
                "consumption": consumption,
                "observed_days": observed_days,
                "average_daily_usage": consumption / observed_days if observed_days > 0 else Decimal("0"),
                "receipts": total_receipts,
                "adjustment_delta": total_adjustment_delta,
                "stock_checks": len(counts),
            }

        return result
