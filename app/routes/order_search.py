import csv
import io
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import selectinload
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


SEARCHED_FIELD_LABELS = [
    "מספר הזמנה", "ספק", "הערות", "מחלקה", "פרויקט",
    "שם מוצר", "מק״ט", "ברקוד", "פרטי פריטים היסטוריים",
]


def _contains_query(value, query):
    return value is not None and query.casefold() in str(value).casefold()


def _matched_search_fields(order, query, tenant_id):
    if not query:
        return []
    matched = set()
    for value, label in (
        (order.order_number, "מספר הזמנה"),
        (order.supplier_name, "ספק"),
        (order.notes, "הערות"),
        (order.department, "מחלקה"),
        (order.project, "פרויקט"),
    ):
        if _contains_query(value, query):
            matched.add(label)

    snapshot_match = False
    for item in order.items or []:
        if not isinstance(item, dict):
            continue
        snapshot_match = snapshot_match or _contains_query(item, query)
        if _contains_query(item.get("product_name") or item.get("name"), query):
            matched.add("שם מוצר")
        if any(_contains_query(item.get(key), query) for key in ("sku", "supplier_sku")):
            matched.add("מק״ט")
        if _contains_query(item.get("barcode"), query):
            matched.add("ברקוד")

    for order_item in order.order_items or []:
        if order_item.tenant_id != tenant_id:
            continue
        product = order_item.product
        if product is None or product.tenant_id != tenant_id:
            continue
        if _contains_query(product.name, query):
            matched.add("שם מוצר")
        if any(_contains_query(getattr(product, field, None), query) for field in ("sku", "supplier_sku")):
            matched.add("מק״ט")
        if _contains_query(getattr(product, "barcode", None), query):
            matched.add("ברקוד")

    if snapshot_match and not ({"שם מוצר", "מק״ט", "ברקוד"} & matched):
        matched.add("פרטי פריטים היסטוריים")
    return [label for label in SEARCHED_FIELD_LABELS if label in matched]


def _missing_order_fields(order, tenant_id):
    missing = []
    if not order.order_number:
        missing.append("מספר הזמנה")
    if not order.supplier_name:
        missing.append("שם ספק")
    has_items = bool(order.items) or any(
        item.tenant_id == tenant_id for item in (order.order_items or [])
    )
    if not has_items:
        missing.append("פירוט פריטים")
    if not order.created_at:
        missing.append("תאריך יצירה")
    return missing


def _active_search_filters(query_text, status, supplier_id, start_date, end_date):
    active = []
    if query_text:
        active.append({"key": "q", "label": "חיפוש", "value": query_text})
    if status:
        status_labels = {
            "draft": "טיוטה", "submitted": "ממתינה לאישור",
            "approved": "אושרה", "sent": "נשלחה לספק",
            "completed": "הושלמה", "cancelled": "בוטלה",
        }
        active.append({"key": "status", "label": "סטטוס", "value": status_labels.get(status, status)})
    if supplier_id is not None:
        active.append({"key": "supplier_id", "label": "מזהה ספק", "value": str(supplier_id)})
    if start_date:
        active.append({"key": "start_date", "label": "מתאריך", "value": start_date.isoformat()})
    if end_date:
        active.append({"key": "end_date", "label": "עד תאריך", "value": end_date.isoformat()})
    return active



def _csv_text(value):
    text = str(value if value is not None else "")
    formula_candidate = text.lstrip(" \t\r\n")
    return "'" + text if formula_candidate.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")) else text


def _build_xlsx_export(orders, filters):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "הזמנות"
    sheet.sheet_view.rightToLeft = True
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:J{len(orders) + 1}"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.print_title_rows = "1:1"

    headers = [
        "מספר הזמנה", "ספק", "סטטוס", "מחלקה", "פרויקט",
        "תאריך יצירה", "תאריך הזמנה מתוכנן", "מטבע", 'סה"כ', "פריטים",
    ]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="243B63")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[1].height = 30

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

        created_at = order.created_at.replace(tzinfo=None) if order.created_at else None
        planned_at = order.planned_order_date
        if planned_at and hasattr(planned_at, "replace") and getattr(planned_at, "tzinfo", None):
            planned_at = planned_at.replace(tzinfo=None)
        sheet.append([
            _csv_text(order.order_number),
            _csv_text(order.supplier_name),
            status_labels.get(order.status, _csv_text(order.status)),
            _csv_text(order.department),
            _csv_text(order.project),
            created_at,
            planned_at,
            _csv_text(order.currency),
            float(order.final_total or 0),
            _csv_text(" | ".join(item_parts)),
        ])
        row = sheet.max_row
        sheet.cell(row, 6).number_format = "dd/mm/yyyy hh:mm"
        sheet.cell(row, 7).number_format = "dd/mm/yyyy"
        sheet.cell(row, 9).number_format = '#,##0.00'
        for column in (1, 2, 3, 4, 5, 8, 10):
            sheet.cell(row, column).data_type = "s"
        for cell in sheet[row]:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (2, 4, 5, 10))

    widths = [20, 28, 20, 20, 20, 20, 20, 10, 16, 55]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    info = workbook.create_sheet("פרטי ייצוא")
    info.sheet_view.rightToLeft = True
    info.append(["פרט", "ערך"])
    info.append(["מספר רשומות", len(orders)])
    for key, label in (
        ("q", "חיפוש"), ("status", "סטטוס"), ("supplier_id", "מזהה ספק"),
        ("start_date", "מתאריך"), ("end_date", "עד תאריך"),
    ):
        value = filters.get(key)
        if value not in (None, ""):
            info.append([label, _csv_text(value)])
    for cell in info[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 48
    for row in info.iter_rows(min_row=2):
        row[1].data_type = "s"

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


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
        if output_format not in ("", "csv", "xlsx"):
            raise BadRequest("Unsupported export format")
        csv_export = output_format == "csv"
        xlsx_export = output_format == "xlsx"
        export_requested = csv_export or xlsx_export
        default_limit = MAX_EXPORT_ROWS if export_requested else DEFAULT_LIMIT
        maximum_limit = MAX_EXPORT_ROWS if export_requested else MAX_LIMIT

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
        if export_requested:
            if offset != 0:
                raise BadRequest("Export must start at offset 0")
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
        if export_requested and total > MAX_EXPORT_ROWS:
            return jsonify({
                "success": False,
                "error": "export_too_large",
                "message": f"CSV export is limited to {MAX_EXPORT_ROWS} orders; narrow the date or status filters.",
                "total": total,
                "maximum": MAX_EXPORT_ROWS,
            }), 413

        orders = db.session.scalars(
            stmt.order_by(Order.created_at.desc(), Order.id.desc())
            .options(selectinload(Order.order_items).selectinload(OrderItem.product))
            .limit(limit).offset(offset)
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

        if xlsx_export:
            filters = {
                "q": query_text,
                "status": status or None,
                "supplier_id": supplier_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
            content = _build_xlsx_export(orders, filters)
            response = Response(
                content,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response.headers["Content-Disposition"] = 'attachment; filename="orders-export.xlsx"'
            response.headers["X-Export-Row-Count"] = str(len(orders))
            return response

        order_payloads = []
        incomplete_order_count = 0
        for order in orders:
            payload = order.to_dict()
            missing_fields = _missing_order_fields(order, current_user.tenant_id)
            if missing_fields:
                incomplete_order_count += 1
            payload["search_provenance"] = {
                "matched_fields": _matched_search_fields(order, query_text, current_user.tenant_id),
                "missing_fields": missing_fields,
            }
            order_payloads.append(payload)

        return jsonify({
            "success": True,
            "orders": order_payloads,
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
            "search_context": {
                "searched_fields": SEARCHED_FIELD_LABELS,
                "active_filters": _active_search_filters(
                    query_text, status, supplier_id, start_date, end_date
                ),
                "data_quality": {
                    "checked_orders": len(orders),
                    "incomplete_count": incomplete_order_count,
                    "scope": "current_page",
                },
            },
        }), 200
    except HTTPException as exc:
        return jsonify({
            "success": False,
            "error": exc.name.lower().replace(" ", "_"),
            "message": exc.description,
        }), exc.code


@order_search_bp.route("/searches", methods=["GET"])
@login_required
def list_saved_order_searches():
    try:
        PermissionService.require_permission("orders.view")
        from app.services.saved_order_search_service import SavedOrderSearchService

        service = SavedOrderSearchService(current_user.tenant_id, current_user.id)
        return jsonify({
            "success": True,
            "saved_searches": [item.to_dict() for item in service.list()],
        }), 200
    except HTTPException as exc:
        return jsonify({
            "success": False,
            "error": exc.name.lower().replace(" ", "_"),
            "message": exc.description,
        }), exc.code


@order_search_bp.route("/searches", methods=["POST"])
@login_required
def create_saved_order_search():
    try:
        PermissionService.require_permission("orders.view")
        from app.services.saved_order_search_service import SavedOrderSearchService

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("Request body must be an object")
        service = SavedOrderSearchService(current_user.tenant_id, current_user.id)
        saved = service.create(data.get("name"), data.get("filters", {}))
        return jsonify({"success": True, "saved_search": saved.to_dict()}), 201
    except HTTPException as exc:
        return jsonify({
            "success": False,
            "error": exc.name.lower().replace(" ", "_"),
            "message": exc.description,
        }), exc.code


@order_search_bp.route("/searches/<int:saved_search_id>", methods=["DELETE"])
@login_required
def delete_saved_order_search(saved_search_id):
    try:
        PermissionService.require_permission("orders.view")
        from app.services.saved_order_search_service import SavedOrderSearchService

        service = SavedOrderSearchService(current_user.tenant_id, current_user.id)
        service.delete(saved_search_id)
        return jsonify({"success": True, "deleted_id": saved_search_id}), 200
    except HTTPException as exc:
        return jsonify({
            "success": False,
            "error": exc.name.lower().replace(" ", "_"),
            "message": exc.description,
        }), exc.code
