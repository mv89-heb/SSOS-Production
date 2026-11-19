import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import String, and_, cast, func, or_, select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.order import Order, VALID_STATUSES
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.permission_service import PermissionService


order_search_bp = Blueprint("order_search", __name__, url_prefix="/api/orders")

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_QUERY_LENGTH = 200
MAX_RANGE_DAYS = 731
MAX_EXPORT_ROWS = 5000


def _csv_text(value):
    text = str(value if value is not None else "")
    formula_candidate = text.lstrip(" \t\r\n")
    return "'" + text if formula_candidate.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")) else text


def _parse_date(value, field):
    if value in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{field} must use YYYY-MM-DD")
    if parsed.isoformat() != value:
        raise BadRequest(f"{field} must use YYYY-MM-DD")
    return parsed


def _like_pattern(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@order_search_bp.route("/search", methods=["GET"])
@login_required
def search_orders():
    try:
        PermissionService.require_permission("orders.view")
        query_text = (request.args.get("q") or "").strip()
        if len(query_text) > MAX_QUERY_LENGTH:
            raise BadRequest(f"q cannot exceed {MAX_QUERY_LENGTH} characters")

        status = (request.args.get("status") or "").strip()
        if status and status not in VALID_STATUSES:
            raise BadRequest("Invalid status filter")

        output_format = (request.args.get("format") or "").strip().lower()
        if output_format not in ("", "csv"):
            raise BadRequest("Unsupported export format")
        csv_export = output_format == "csv"
        default_limit = MAX_EXPORT_ROWS if csv_export else DEFAULT_LIMIT
        maximum_limit = MAX_EXPORT_ROWS if csv_export else MAX_LIMIT

        try:
            limit = int(request.args.get("limit", default_limit))
            offset = int(request.args.get("offset", 0))
        except (TypeError, ValueError):
            raise BadRequest("limit and offset must be integers")
        supplier_raw = request.args.get("supplier_id")
        try:
            supplier_id = int(supplier_raw) if supplier_raw not in (None, "") else None
        except (TypeError, ValueError):
            raise BadRequest("supplier_id must be an integer")
        if limit < 1 or offset < 0 or (supplier_id is not None and supplier_id < 1):
            raise BadRequest("limit and supplier_id must be positive; offset cannot be negative")
        limit = min(limit, maximum_limit)
        if csv_export:
            if offset != 0:
                raise BadRequest("CSV export must start at offset 0")
            limit = MAX_EXPORT_ROWS

        start_date = _parse_date(request.args.get("start_date"), "start_date")
        end_date = _parse_date(request.args.get("end_date"), "end_date")
        if start_date and end_date and end_date < start_date:
            raise BadRequest("end_date must not be earlier than start_date")
        if start_date and end_date and (end_date - start_date).days > MAX_RANGE_DAYS:
            raise BadRequest(f"Date range cannot exceed {MAX_RANGE_DAYS} days")

        stmt = select(Order).where(Order.tenant_id == current_user.tenant_id)
        if status:
            stmt = stmt.where(Order.status == status)
        if supplier_id is not None:
            stmt = stmt.where(Order.supplier_id == supplier_id)
        if start_date:
            start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
            stmt = stmt.where(Order.created_at >= start_at)
        if end_date:
            end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
            stmt = stmt.where(Order.created_at < end_at)
        if query_text:
            pattern = _like_pattern(query_text)
            stmt = stmt.where(or_(
                Order.order_number.ilike(pattern, escape="\\"),
                Order.supplier_name.ilike(pattern, escape="\\"),
                Order.notes.ilike(pattern, escape="\\"),
                Order.department.ilike(pattern, escape="\\"),
                Order.project.ilike(pattern, escape="\\"),
                cast(Order.items, String).ilike(pattern, escape="\\"),
                Order.order_items.any(and_(
                    OrderItem.tenant_id == current_user.tenant_id,
                    OrderItem.product.has(and_(
                        Product.tenant_id == current_user.tenant_id,
                        or_(
                            Product.name.ilike(pattern, escape="\\"),
                            Product.sku.ilike(pattern, escape="\\"),
                            Product.supplier_sku.ilike(pattern, escape="\\"),
                            Product.barcode.ilike(pattern, escape="\\"),
                        ),
                    )),
                )),
            ))

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = db.session.scalar(count_stmt) or 0
        if csv_export and total > MAX_EXPORT_ROWS:
            return jsonify({
                "success": False,
                "error": "export_too_large",
                "message": f"CSV export is limited to {MAX_EXPORT_ROWS} orders; narrow the date or status filters.",
                "total": total,
                "maximum": MAX_EXPORT_ROWS,
            }), 413

        orders = db.session.scalars(
            stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
        ).all()

        if csv_export:
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow([
                "מספר הזמנה", "ספק", "סטטוס", "מחלקה", "פרויקט",
                "תאריך יצירה", "תאריך הזמנה מתוכנן", "מטבע", 'סה"כ', "פריטים",
            ])
            status_labels = {
                "draft": "טיוטה", "submitted": "ממתינה לאישור",
                "approved": "אושרה", "sent": "נשלחה לספק",
                "completed": "הושלמה", "cancelled": "בוטלה",
            }
            for order in orders:
                item_parts = []
                for index, item in enumerate(order.items or []):
                    if not isinstance(item, dict):
                        continue
                    product_name = item.get("product_name") or item.get("name") or f"פריט {index + 1}"
                    quantity = item.get("quantity", "")
                    unit = item.get("unit") or ""
                    item_parts.append(f"{product_name} × {quantity} {unit}".strip())
                writer.writerow([
                    _csv_text(order.order_number),
                    _csv_text(order.supplier_name),
                    status_labels.get(order.status, _csv_text(order.status)),
                    _csv_text(order.department),
                    _csv_text(order.project),
                    order.created_at.isoformat() if order.created_at else "",
                    order.planned_order_date.isoformat() if order.planned_order_date else "",
                    _csv_text(order.currency),
                    float(order.final_total or 0),
                    _csv_text(" | ".join(item_parts)),
                ])
            response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
            response.headers["Content-Disposition"] = 'attachment; filename="orders-export.csv"'
            response.headers["X-Export-Row-Count"] = str(len(orders))
            return response

        return jsonify({
            "success": True,
            "orders": [order.to_dict() for order in orders],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(orders) < total,
            },
            "filters": {
                "q": query_text,
                "status": status or None,
                "supplier_id": supplier_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        }), 200
    except HTTPException as exc:
        return jsonify({
            "success": False,
            "error": exc.name.lower().replace(" ", "_"),
            "message": exc.description,
        }), exc.code
