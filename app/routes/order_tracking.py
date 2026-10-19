from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from app.extensions import db
from app.models.order import Order, REMINDER_PENDING
from app.models.order_tracking_event import OrderTrackingEvent
from app.services.permission_service import PermissionService

order_tracking_bp = Blueprint("order_tracking", __name__, url_prefix="/api/orders")

EVENT_TYPES = {
    "email_sent", "supplier_confirmed", "in_transit", "partial_delivery",
    "fully_delivered", "issue", "credit_pending", "other",
}


def _error(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _parse_datetime(value, field, required=False):
    if value in (None, ""):
        if required:
            raise BadRequest(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise BadRequest(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BadRequest(f"{field} must be an ISO timestamp")
    if parsed.tzinfo is None:
        raise BadRequest(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _get_order(order_id):
    order = db.session.scalar(select(Order).where(
        Order.id == order_id,
        Order.tenant_id == current_user.tenant_id,
    ))
    if order is None:
        raise NotFound("Order not found")
    return order


@order_tracking_bp.route("/<int:order_id>/tracking-events", methods=["GET"])
@login_required
def list_tracking_events(order_id):
    try:
        _get_order(order_id)
        events = db.session.scalars(select(OrderTrackingEvent).where(
            OrderTrackingEvent.tenant_id == current_user.tenant_id,
            OrderTrackingEvent.order_id == order_id,
        ).order_by(OrderTrackingEvent.occurred_at.desc(), OrderTrackingEvent.id.desc())).all()
        return jsonify({"success": True, "events": [event.to_dict() for event in events]})
    except HTTPException as exc:
        return _error(exc)


@order_tracking_bp.route("/<int:order_id>/tracking-events", methods=["POST"])
@login_required
def create_tracking_event(order_id):
    try:
        PermissionService.require_role_at_least("employee")
        order = _get_order(order_id)
        data = request.get_json(silent=True) or {}
        event_type = str(data.get("event_type") or "").strip()
        if event_type not in EVENT_TYPES:
            raise BadRequest("event_type is not supported")
        summary = str(data.get("summary") or "").strip()
        if not summary or len(summary) > 500:
            raise BadRequest("summary is required and must be at most 500 characters")
        details = str(data.get("details") or "").strip()[:5000] or None
        contact_name = str(data.get("contact_name") or "").strip()[:200] or None
        occurred_at = _parse_datetime(data.get("occurred_at"), "occurred_at") or datetime.now(timezone.utc)
        follow_up = _parse_datetime(data.get("next_follow_up_at"), "next_follow_up_at")
        event = OrderTrackingEvent(
            tenant_id=current_user.tenant_id,
            order_id=order.id,
            event_type=event_type,
            summary=summary,
            details=details,
            contact_name=contact_name,
            occurred_at=occurred_at,
            next_follow_up_at=follow_up,
            created_by=current_user.id,
        )
        db.session.add(event)
        if follow_up is not None:
            # Feed the existing order-reminder queue so the follow-up is visible
            # in the system's current reminder workflow.
            order.next_reminder_at = follow_up
            order.reminder_state = REMINDER_PENDING
        db.session.commit()
        return jsonify({"success": True, "event": event.to_dict()}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
