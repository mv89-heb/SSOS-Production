from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.order import Order, STATUS_APPROVED, STATUS_SENT, STATUS_COMPLETED
from app.models.order_item import OrderItem
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoicePayment
from app.services.permission_service import PermissionService


procurement_analytics_bp = Blueprint(
    "procurement_analytics", __name__, url_prefix="/api/procurement-analytics"
)

ORDERED_STATUSES = (STATUS_APPROVED, STATUS_SENT, STATUS_COMPLETED)
MAX_RANGE_DAYS = 731


def _parse_date(value: str | None, field: str, default: date) -> date:
    if value is None or value == "":
        return default
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{field} must use YYYY-MM-DD")


def _money(value) -> Decimal:
    try:
        result = Decimal(str(value or 0))
    except Exception:
        return Decimal("0")
    return result if result.is_finite() else Decimal("0")


def _serialize_groups(groups):
    output = []
    for (supplier_id, supplier_name, category, currency), values in sorted(
        groups.items(), key=lambda entry: (entry[0][2], entry[0][1].casefold(), entry[0][3])
    ):
        output.append({
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "category": category,
            "currency": currency,
            "total": float(values["total"].quantize(Decimal("0.01"))),
            "count": len(values["documents"]),
            "documents": values["documents"],
        })
    return output


def _add(groups, supplier_id, supplier_name, category, currency, amount, document):
    currency = (currency or "ILS").upper()
    key = (supplier_id, supplier_name or "ספק לא ידוע", category or "לא מסווג", currency)
    group = groups[key]
    group["total"] += amount
    group["documents"].append(document)


def _supplier_reliability(tenant_id: int, start_at: datetime, end_at: datetime):
    """Measure only completed orders with recorded posted receipts and dates."""
    rows = db.session.execute(
        select(Order, Supplier)
        .outerjoin(
            Supplier,
            (Supplier.id == Order.supplier_id) & (Supplier.tenant_id == tenant_id),
        )
        .where(
            Order.tenant_id == tenant_id,
            Order.status == STATUS_COMPLETED,
            Order.created_at >= start_at,
            Order.created_at < end_at,
        )
        .order_by(Order.id.asc())
    ).all()
    if not rows:
        return []

    orders = [row[0] for row in rows]
    supplier_by_order = {order.id: supplier for order, supplier in rows}
    order_ids = [order.id for order in orders]
    receipts = db.session.scalars(
        select(Receipt).where(
            Receipt.tenant_id == tenant_id,
            Receipt.order_id.in_(order_ids),
            Receipt.status == RECEIPT_POSTED,
            or_(Receipt.received_at.is_(None), Receipt.received_at < end_at),
        ).order_by(Receipt.received_at.asc(), Receipt.id.asc())
    ).all()
    receipt_by_order = defaultdict(list)
    receipt_ids = []
    for receipt in receipts:
        receipt_by_order[receipt.order_id].append(receipt)
        receipt_ids.append(receipt.id)

    received_by_item = defaultdict(Decimal)
    if receipt_ids:
        receipt_lines = db.session.scalars(
            select(ReceiptItem).where(
                ReceiptItem.tenant_id == tenant_id,
                ReceiptItem.receipt_id.in_(receipt_ids),
            )
        ).all()
        for line in receipt_lines:
            received_by_item[line.order_item_id] += Decimal(str(line.quantity))

    order_items = db.session.scalars(
        select(OrderItem).where(
            OrderItem.tenant_id == tenant_id,
            OrderItem.order_id.in_(order_ids),
        ).order_by(OrderItem.order_id.asc(), OrderItem.id.asc())
    ).all()
    items_by_order = defaultdict(list)
    for item in order_items:
        items_by_order[item.order_id].append(item)

    metrics = {}
    for order in orders:
        supplier = supplier_by_order.get(order.id)
        supplier_id = supplier.id if supplier else order.supplier_id
        supplier_name = supplier.name if supplier else order.supplier_name
        category = supplier.supplier_category if supplier else "לא מסווג"
        key = (supplier_id, supplier_name or "ספק לא ידוע", category or "לא מסווג")
        metric = metrics.setdefault(key, {
            "completed_orders": 0,
            "delivery_sample_size": 0,
            "late_orders": 0,
            "shortage_sample_size": 0,
            "short_orders": 0,
            "missing_planned_date": 0,
            "missing_receipt_date": 0,
            "orders_without_posted_receipt": 0,
        })
        metric["completed_orders"] += 1
        if not order.planned_order_date:
            metric["missing_planned_date"] += 1

        order_receipts = receipt_by_order.get(order.id, [])
        if not order_receipts:
            metric["orders_without_posted_receipt"] += 1
            metric["missing_receipt_date"] += 1
            continue

        dated_receipts = [r.received_at for r in order_receipts if r.received_at is not None]
        if not dated_receipts:
            metric["missing_receipt_date"] += 1
        elif order.planned_order_date:
            completion_date = max(dated_receipts).date()
            metric["delivery_sample_size"] += 1
            if completion_date > order.planned_order_date:
                metric["late_orders"] += 1

        lines = items_by_order.get(order.id, [])
        if lines:
            metric["shortage_sample_size"] += 1
            has_shortage = any(
                received_by_item.get(item.id, Decimal("0")) < Decimal(str(item.quantity))
                for item in lines
            )
            if has_shortage:
                metric["short_orders"] += 1

    result = []
    for (supplier_id, supplier_name, category), metric in metrics.items():
        delivery_n = metric["delivery_sample_size"]
        shortage_n = metric["shortage_sample_size"]
        result.append({
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "category": category,
            **metric,
            "late_rate_percent": round(metric["late_orders"] * 100 / delivery_n, 1) if delivery_n else None,
            "shortage_rate_percent": round(metric["short_orders"] * 100 / shortage_n, 1) if shortage_n else None,
            "credit_adjustment_frequency": None,
            "credit_adjustment_data_available": False,
            "credit_adjustment_note": "אין במערכת קישור מובנה בין זיכויים/התאמות לבין ספק והזמנה; המדד אינו מחושב.",
        })
    return sorted(result, key=lambda row: row["supplier_name"].casefold())


@procurement_analytics_bp.route("/spend", methods=["GET"])
@login_required
def procurement_spend():
    try:
        PermissionService.require_permission("orders.view")
        today = datetime.now(timezone.utc).date()
        start_date = _parse_date(request.args.get("start_date"), "start_date", today.replace(day=1))
        end_date = _parse_date(request.args.get("end_date"), "end_date", today)
        if end_date < start_date:
            raise BadRequest("end_date must not be earlier than start_date")
        if (end_date - start_date).days > MAX_RANGE_DAYS:
            raise BadRequest(f"Date range cannot exceed {MAX_RANGE_DAYS} days")

        start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        tenant_id = current_user.tenant_id

        ordered_groups = defaultdict(lambda: {"total": Decimal("0"), "documents": []})
        orders = db.session.execute(
            select(Order, Supplier)
            .outerjoin(
                Supplier,
                (Supplier.id == Order.supplier_id) & (Supplier.tenant_id == tenant_id),
            )
            .where(
                Order.tenant_id == tenant_id,
                Order.status.in_(ORDERED_STATUSES),
                Order.created_at >= start_at,
                Order.created_at < end_at,
            )
            .order_by(Order.created_at.asc(), Order.id.asc())
        ).all()
        for order, supplier in orders:
            amount = _money(order.final_total)
            _add(
                ordered_groups, order.supplier_id, order.supplier_name,
                supplier.supplier_category if supplier else None, order.currency,
                amount, {
                    "id": order.id, "reference": order.order_number,
                    "date": order.created_at.date().isoformat() if order.created_at else None,
                    "status": order.status, "amount": float(amount),
                },
            )

        invoiced_groups = defaultdict(lambda: {"total": Decimal("0"), "documents": []})
        invoices = db.session.execute(
            select(SupplierInvoice, Supplier)
            .join(Supplier, (Supplier.id == SupplierInvoice.supplier_id) & (Supplier.tenant_id == tenant_id))
            .where(
                SupplierInvoice.tenant_id == tenant_id,
                SupplierInvoice.invoice_date >= start_date,
                SupplierInvoice.invoice_date <= end_date,
            )
            .order_by(SupplierInvoice.invoice_date.asc(), SupplierInvoice.id.asc())
        ).all()
        for invoice, supplier in invoices:
            amount = _money(invoice.amount)
            _add(
                invoiced_groups, supplier.id, supplier.name, supplier.supplier_category,
                invoice.currency, amount, {
                    "id": invoice.id, "reference": invoice.invoice_number,
                    "date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    "status": invoice.approval_status, "amount": float(amount),
                    "order_id": invoice.order_id,
                },
            )

        paid_groups = defaultdict(lambda: {"total": Decimal("0"), "documents": []})
        payments = db.session.execute(
            select(SupplierInvoicePayment, SupplierInvoice, Supplier)
            .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoicePayment.invoice_id)
            .join(Supplier, Supplier.id == SupplierInvoice.supplier_id)
            .where(
                SupplierInvoicePayment.tenant_id == tenant_id,
                SupplierInvoice.tenant_id == tenant_id,
                SupplierInvoicePayment.payment_date >= start_date,
                SupplierInvoicePayment.payment_date <= end_date,
            )
            .order_by(SupplierInvoicePayment.payment_date.asc(), SupplierInvoicePayment.id.asc())
        ).all()
        for payment, invoice, supplier in payments:
            amount = _money(payment.amount)
            _add(
                paid_groups, supplier.id, supplier.name, supplier.supplier_category,
                invoice.currency, amount, {
                    "id": payment.id, "reference": payment.reference or invoice.invoice_number,
                    "date": payment.payment_date.isoformat(),
                    "status": "paid", "amount": float(amount),
                    "invoice_id": invoice.id, "order_id": invoice.order_id,
                },
            )

        def totals(groups):
            values = defaultdict(Decimal)
            for (_, _, _, currency), group in groups.items():
                values[currency] += group["total"]
            return {currency: float(value.quantize(Decimal("0.01"))) for currency, value in sorted(values.items())}

        return jsonify({
            "success": True,
            "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "definitions": {
                "ordered": "Approved, sent and completed purchase orders by order creation date. Draft, submitted and cancelled orders are excluded.",
                "invoiced": "Recorded supplier invoices by invoice date. This is not added to ordered spend.",
                "paid": "Recorded invoice payments by payment date. Partial payments are counted only when paid.",
                "currency": "Totals are separated by currency; currencies are never converted or summed together.",
                "reliability": "Supplier reliability uses completed orders created in the selected period. Lateness is measured from planned date to the last posted receipt; shortage means at least one line has a recorded received quantity below the ordered quantity. Missing dates and sample sizes are shown; credit/adjustment frequency is not available without structured linkage.",
            },
            "ordered": {"totals_by_currency": totals(ordered_groups), "by_supplier": _serialize_groups(ordered_groups)},
            "invoiced": {"totals_by_currency": totals(invoiced_groups), "by_supplier": _serialize_groups(invoiced_groups)},
            "paid": {"totals_by_currency": totals(paid_groups), "by_supplier": _serialize_groups(paid_groups)},
            "supplier_reliability": _supplier_reliability(tenant_id, start_at, end_at),
        }), 200
    except HTTPException as exc:
        return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code
