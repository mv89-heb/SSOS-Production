from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from sqlalchemy import and_, or_, select

from app.extensions import db
from app.models.order import Order, STATUS_COMPLETED, STATUS_SENT
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.inventory_calendar_service import InventoryCalendarService


class OrderHistoryForecastService:
    """Forecast from supplier-issued orders, normalized to the product stock unit.

    Draft/cancelled/internal orders and physical stock counts are excluded.
    Carton quantities are converted using the pack-size snapshot captured on
    each order line; missing or inconsistent conversion data blocks a suggestion.
    """

    INCLUDED_STATUSES = (STATUS_SENT, STATUS_COMPLETED)

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    @staticmethod
    def _week_start(value: date) -> date:
        return value - timedelta(days=value.weekday())

    @staticmethod
    def _positive_pack_size(value):
        if isinstance(value, bool):
            return None
        try:
            parsed_decimal = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not parsed_decimal.is_finite() or parsed_decimal != parsed_decimal.to_integral_value():
            return None
        parsed = int(parsed_decimal)
        return parsed if parsed > 0 else None

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
                or_(
                    and_(
                        Order.planned_order_date >= start_date,
                        Order.planned_order_date <= end_date,
                    ),
                    and_(
                        Order.planned_order_date.is_(None),
                        Order.created_at >= datetime.combine(start_date, time.min),
                        Order.created_at < datetime.combine(end_date + timedelta(days=1), time.min),
                    ),
                ),
            )
            .order_by(Order.created_at.asc(), Order.id.asc(), OrderItem.id.asc())
        ).all()

        weekly_quantities: dict[int, dict[date, Decimal]] = {}
        product_meta: dict[int, dict] = {}
        order_ids: dict[int, set[int]] = {}
        order_weeks: dict[int, set[date]] = {}
        conversion_issues: dict[int, int] = {}

        for order, item, product in rows:
            effective_date = order.planned_order_date or (
                order.created_at.date() if order.created_at else None
            )
            if effective_date is None or not (start_date <= effective_date <= end_date):
                continue

            product_id = int(item.product_id)
            snapshot = item.product_snapshot if isinstance(item.product_snapshot, dict) else {}
            stock_unit = str(snapshot.get("stock_unit") or product.unit or "יחידה לא הוגדרה").strip()
            if product_id not in product_meta:
                product_meta[product_id] = {
                    "product_id": product_id,
                    "product_name": product.name,
                    "unit": stock_unit,
                    "units_per_carton": product.units_per_carton,
                }
                weekly_quantities[product_id] = {}
                conversion_issues[product_id] = 0
            elif product_meta[product_id]["unit"] != stock_unit:
                conversion_issues[product_id] += 1
                continue

            try:
                quantity = Decimal(str(item.quantity or 0))
            except (InvalidOperation, TypeError, ValueError):
                conversion_issues[product_id] += 1
                continue
            if not quantity.is_finite() or quantity <= 0:
                continue

            quantity_unit = snapshot.get("quantity_unit")
            ordered_unit = str(snapshot.get("unit") or "").strip()
            is_carton_quantity = quantity_unit == "carton" or (
                quantity_unit in (None, "") and ordered_unit == "קרטון"
            )
            if is_carton_quantity:
                # Never use today's catalog pack size to reinterpret an old order.
                # Only the immutable per-order snapshot can safely convert cartons.
                pack_size = self._positive_pack_size(snapshot.get("units_per_carton"))
                if pack_size is None:
                    conversion_issues[product_id] += 1
                    continue
                quantity *= Decimal(pack_size)
            elif quantity_unit not in (None, ""):
                conversion_issues[product_id] += 1
                continue

            week = self._week_start(effective_date)
            weekly_quantities[product_id][week] = (
                weekly_quantities[product_id].get(week, Decimal("0")) + quantity
            )
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
            normal_average = (
                normal_total / Decimal(len(normal_week_starts))
                if normal_week_starts else Decimal("0")
            )
            observed_orders = len(order_ids.get(product_id, set()))
            observed_weeks = len(order_weeks.get(product_id, set()))
            observed_normal_weeks = sum(
                1 for week in normal_week_starts
                if weekly.get(week, Decimal("0")) > 0
            )
            has_unit_issues = conversion_issues.get(product_id, 0) > 0
            enough_history = (
                not has_unit_issues
                and observed_orders >= 2
                and observed_weeks >= 2
                and observed_normal_weeks >= 1
            )
            recommended_exact = normal_average * target_multiplier if enough_history else Decimal("0")
            # OrderService accepts integer quantities only; always round up to avoid
            # silently truncating a forecast (for example 19.6) to an under-order (19).
            recommended = int(recommended_exact.to_integral_value(rounding=ROUND_CEILING))
            if has_unit_issues:
                readiness_reason = "unit_conversion_requires_review"
            elif not enough_history:
                readiness_reason = "insufficient_order_history"
            else:
                readiness_reason = None

            result.append({
                **product_meta[product_id],
                "order_count": observed_orders,
                "weeks_with_orders": observed_weeks,
                "normal_weeks_with_orders": observed_normal_weeks,
                "normal_weeks_in_period": len(normal_week_starts),
                "boosted_weeks_in_period": len(boosted_week_starts),
                "unit_conversion_issues": conversion_issues.get(product_id, 0),
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
                "recommended_quantity": recommended,
                "recommended_quantity_exact": round(float(recommended_exact), 3),
                "target_week_multiplier": float(target_multiplier),
                "data_ready": enough_history,
                "readiness_reason": readiness_reason,
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
            "quantity_basis": "product_stock_unit",
            "excluded_statuses": ["draft", "cancelled", "submitted", "approved"],
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
