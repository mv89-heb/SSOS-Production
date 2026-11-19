from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_, select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.order import Order, VALID_STATUSES
from app.services.permission_service import PermissionService


order_search_bp = Blueprint("order_search", __name__, url_prefix="/api/orders")

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_QUERY_LENGTH = 200
MAX_RANGE_DAYS = 731


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

        try:
            limit = int(request.args.get("limit", DEFAULT_LIMIT))
            offset = int(request.args.get("offset", 0))
            supplier_id = request.args.get("supplier_id", type=int)
        except (TypeError, ValueError):
            raise BadRequest("limit, offset and supplier_id must be integers")
        if limit < 1 or offset < 0 or (supplier_id is not None and supplier_id < 1):
            raise BadRequest("limit and supplier_id must be positive; offset cannot be negative")
        limit = min(limit, MAX_LIMIT)

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
            ))

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = db.session.scalar(count_stmt) or 0
        orders = db.session.scalars(
            stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
        ).all()
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
