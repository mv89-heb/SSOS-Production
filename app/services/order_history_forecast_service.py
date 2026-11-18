from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.order import (
    Order,
    STATUS_APPROVED,
    STATUS_COMPLETED,
    STATUS_SENT,
    STATUS_SUBMITTED,
)
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.inventory_calendar_service import InventoryCalendarService


class OrderHistoryForecastService:
    """Forecast supplier order quantities from issued operational orders only.

    Draft/cancelled orders and physical stock counts are deliberately excluded.
    Quantities remain in the product's recorded order unit; this service never
    guesses carton conversions.
    """

    INCLUDED_STATUSES = (
        STATUS_SUBMITTED,
        STATUS_APPROVED,
        STATUS_SENT,
        STATUS_COMPLETED,
    )

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _week_start(value: date) -> date:
        return value - timedelta(days=value.weekday())

    def supplier_forecast(
        self,
        supplier_id: int,
        *,
        start_date: date,
        end_date: date,
        target_date: date | None = None,
    ) -> dict:
        if end_date < start_date:
            raise ValueError("end_date must not be earlier than start_date")

        target_date = target_date or date.today()
        config = InventoryCalendarService._seasonality_config()
        cycle_weeks = config["cycle_weeks"]
        normal_weeks_per_cycle = config["normal_weeks"]
        uplift = config["uplift"]

        first_week = self._week_start(start_date)
        last_week = self._week_start(end_date)
        week_starts = []
        cursor = first_week
        while cursor <= last_week:
            week_starts.append(cursor)
            cursor += timedelta(days=7)

        normal_week_starts = [
            week for week in week_starts
            if (week - date(2020, 1, 6)).days // 7 % cycle_weeks < normal_weeks_per_cycle
        ]
        boosted_week_starts = [week for week in week_starts if week not in normal_week_starts]

        rows = db.session.execute(
            select(Order, OrderItem, Product)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(
                Order.tenant_id == self.tenant_id,
                OrderItem.tenant_id == self.tenant_id,
                Product.tenant_id == self.tenant_id,
                Order.supplier_id == supplier_id,
                Order.status.in_(self.INCLUDED_STATUSES),
            )
            .order_by(Order.created_at.asc(), Order.id.asc(), OrderItem.id.asc())
        ).all()

        weekly_quantities: dict[int, dict[date, Decimal]] = {}
        product_meta: dict[int, dict] = {}
        order_ids: dict[int, set[int]] = {}
        order_weeks: dict[int, set[date]] = {}

        for order, item, product in rows:
            effective_date = order.planned_order_date or (
                order.created_at.date() if order.created_at else None
            )
            if effective_date is None or not (start_date <= effective_date <= end_date):
                continue

            product_id = int(item.product_id)
            quantity = Decimal(str(item.quantity or 0))
            if not quantity.is_finite() or quantity <= 0:
                continue

            week = self._week_start(effective_date)
            weekly_quantities.setdefault(product_id, {})
            weekly_quantities[product_id][week] = (
                weekly_quantities[product_id].get(week, Decimal("0")) + quantity
            )
            product_meta[product_id] = {
                "product_id": product_id,
                "product_name": product.name,
                "unit": (item.product_snapshot or {}).get("unit") or product.unit or "יחידה לא הוגדרה",
                "units_per_carton": product.units_per_carton,
            }
            order_ids.setdefault(product_id, set()).add(order.id)
            order_weeks.setdefault(product_id, set()).add(week)

        target_multiplier = InventoryCalendarService._seasonal_multiplier_for_date(
            target_date, config
        )
        result = []
        for product_id, weekly in weekly_quantities.items():
            normal_total = sum(
                (weekly.get(week, Decimal("0")) for week in normal_week_starts),
                Decimal("0"),
            )
            boosted_total = sum(
                (weekly.get(week, Decimal("0")) for week in boosted_week_starts),
                Decimal("0"),
            )
            normal_average = (
                normal_total / Decimal(len(normal_week_starts))
                if normal_week_starts else Decimal("0")
            )
            observed_orders = len(order_ids.get(product_id, set()))
            observed_weeks = len(order_weeks.get(product_id, set()))
            enough_history = observed_orders >= 2 and observed_weeks >= 2 and bool(normal_week_starts)
            recommended = normal_average * target_multiplier if enough_history else Decimal("0")
            result.append({
                **product_meta[product_id],
                "order_count": observed_orders,
                "weeks_with_orders": observed_weeks,
                "normal_weeks_in_period": len(normal_week_starts),
                "boosted_weeks_in_period": len(boosted_week_starts),
                "normal_weekly_average": round(float(normal_average), 3),
                "boosted_weekly_forecast": round(float(normal_average * uplift), 3),
                "average_weekly_forecast": round(float(
                    normal_average
                    * (
                        Decimal(normal_weeks_per_cycle)
                        + Decimal(config["boosted_weeks"]) * uplift
                    )
                    / Decimal(cycle_weeks)
                ), 3),
                "recommended_quantity": round(float(recommended), 3),
                "target_week_multiplier": float(target_multiplier),
                "data_ready": enough_history,
                "readiness_reason": None if enough_history else "insufficient_order_history",
            })

        result.sort(
            key=lambda row: (
                not row["data_ready"],
                -row["normal_weekly_average"],
                row["product_name"].casefold(),
            )
        )
        return {
            "supplier_id": supplier_id,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "target_date": target_date.isoformat(),
            "source": "issued_operational_orders",
            "excluded_statuses": ["draft", "cancelled"],
            "seasonality": {
                "cycle_weeks": cycle_weeks,
                "normal_weeks": normal_weeks_per_cycle,
                "boosted_weeks": config["boosted_weeks"],
                "boosted_week_multiplier": float(uplift),
                "target_week_multiplier": float(target_multiplier),
            },
            "order_count": len({order_id for values in order_ids.values() for order_id in values}),
            "products": result,
        }
