from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db, limiter
from app.models.notification import Notification
from app.models.order import Order
from app.services.audit_service import AuditService
from app.services.google_calendar_link_service import get_event_html_link
from app.services import google_calendar_service as gcal
from app.services.web_push_service import public_key, remove_subscription, save_subscription, send_to_user

web_push_bp = Blueprint("web_push", __name__, url_prefix="/api/push")


@web_push_bp.route("/public-key", methods=["GET"])
def get_public_key():
    return jsonify({"success": True, "public_key": public_key()})


@web_push_bp.route("/subscribe", methods=["POST"])
@login_required
@limiter.limit("20/minute", methods=["POST"])
def subscribe():
    payload = request.get_json(silent=True) or {}
    try:
        subscription = save_subscription(current_user.id, current_user.tenant_id, payload, request.headers.get("User-Agent"))
    except ValueError as exc:
        return jsonify({"success": False, "error": "invalid_subscription", "message": str(exc)}), 400
    return jsonify({"success": True, "subscription": subscription.to_dict()})


@web_push_bp.route("/unsubscribe", methods=["POST"])
@login_required
@limiter.limit("20/minute", methods=["POST"])
def unsubscribe():
    payload = request.get_json(silent=True) or {}
    endpoint = str(payload.get("endpoint") or "").strip()
    if not endpoint:
        return jsonify({"success": False, "error": "endpoint_required"}), 400
    remove_subscription(current_user.id, endpoint)
    return jsonify({"success": True})


@web_push_bp.after_app_request
def reminder_change_push(response):
    """Emit one mobile push after a reminder event has been successfully persisted."""
    if not current_user.is_authenticated or response.status_code != 200:
        return response
    match = re.match(r"^/api/order-reminders/orders/(\d+)/(activate|manual|snooze)$", request.path)
    if not match:
        return response

    try:
        order_id = int(match.group(1))
        operation = match.group(2)
        order = db.session.execute(
            select(Order).where(Order.id == order_id, Order.tenant_id == current_user.tenant_id, Order.user_id == current_user.id)
        ).scalar_one_or_none()
        if order is None or not order.next_reminder_at:
            return response

        if not order.google_calendar_event_url and order.google_calendar_event_id:
            connection = gcal.get_connection(current_user.id, current_user.tenant_id)
            order.google_calendar_event_url = get_event_html_link(connection, order.google_calendar_event_id)
            if order.google_calendar_event_url:
                db.session.commit()

        notification_type = "reminder_created" if operation in ("activate", "manual") else "reminder_rescheduled"
        title = "התזכורת נוצרה" if notification_type == "reminder_created" else "התזכורת עודכנה"
        local_time = order.next_reminder_at.replace(tzinfo=timezone.utc).astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M")
        message = (
            f"התזכורת להזמנה {order.order_number} נוספה ל-Google Calendar."
            if notification_type == "reminder_created"
            else f"התזכורת להזמנה {order.order_number} נדחתה ל-{local_time}."
        )
        action_url = order.google_calendar_event_url or (
            current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") + f"/dashboard/orders/{order.id}"
        )

        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
        duplicate = db.session.execute(
            select(Notification.id).where(
                Notification.user_id == current_user.id,
                Notification.tenant_id == current_user.tenant_id,
                Notification.notification_type == notification_type,
                Notification.created_at >= recent_cutoff,
                Notification.message.like(f"%{order.order_number}%"),
            ).limit(1)
        ).scalar_one_or_none()
        if duplicate:
            return response

        notification = Notification(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            title=title,
            message=message,
            status="unread",
            action_url=action_url,
            notification_type=notification_type,
        )
        db.session.add(notification)
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            notification_type,
            title=title,
            metadata={"order_id": order.id, "order_number": order.order_number, "calendar_event_url": order.google_calendar_event_url},
        )
        db.session.commit()

        send_to_user(
            current_user.id,
            {
                "title": title,
                "body": message,
                "url": action_url,
                "notification_id": notification.id,
                "order_id": order.id,
                "type": notification_type,
            },
        )
    except Exception:
        current_app.logger.exception("Failed to send reminder creation mobile notification")
        db.session.rollback()
    return response
