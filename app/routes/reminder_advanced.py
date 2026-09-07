from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.models.order import Order, REMINDER_PENDING
from app.repositories.base_repository import BaseRepository
from app.services.audit_service import AuditService

reminder_advanced_bp = Blueprint("reminder_advanced", __name__, url_prefix="/api/order-reminders")


class _ReminderRepo(BaseRepository):
    model = Order


def _owned(order_id: int):
    order = _ReminderRepo(tenant_id=current_user.tenant_id).get_by_id_for_update(order_id)
    if order is None or order.user_id != current_user.id:
        raise NotFound("Order not found")
    if order.status in ("sent", "completed", "cancelled"):
        raise BadRequest("Reminder cannot be changed for a closed order")
    return order


@reminder_advanced_bp.route("/orders/<int:order_id>/recurrence", methods=["POST"])
@login_required
def set_recurrence(order_id: int):
    try:
        order = _owned(order_id)
        data = request.get_json(silent=True) or {}
        every_minutes = int(data.get("every_minutes", 0))
        max_occurrences = int(data.get("max_occurrences", 0))
        if every_minutes and every_minutes < 5:
            raise BadRequest("every_minutes must be 0 or at least 5")
        if max_occurrences < 0:
            raise BadRequest("max_occurrences cannot be negative")
        snapshot = dict(order.reminder_rules_snapshot or {})
        snapshot["recurrence"] = {"every_minutes": every_minutes, "max_occurrences": max_occurrences}
        snapshot["occurrences"] = 0
        order.reminder_rules_snapshot = snapshot
        order.reminder_state = REMINDER_PENDING
        db.session.commit()
        AuditService.log_event(current_user.tenant_id, current_user.id, "reminder_recurrence_configured", title="הוגדרה תזכורת חוזרת", metadata={"order_id": order.id, "every_minutes": every_minutes, "max_occurrences": max_occurrences})
        db.session.commit()
        return jsonify({"success": True, "order": order.to_dict()})
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "invalid_recurrence"}), 400
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, BadRequest):
            return jsonify({"success": False, "error": "bad_request", "message": exc.description}), 400
        if isinstance(exc, NotFound):
            return jsonify({"success": False, "error": "not_found", "message": exc.description}), 404
        raise


@reminder_advanced_bp.route("/orders/<int:order_id>/escalation", methods=["POST"])
@login_required
def set_escalation(order_id: int):
    try:
        order = _owned(order_id)
        data = request.get_json(silent=True) or {}
        after_occurrences = int(data.get("after_occurrences", 0))
        if after_occurrences < 0:
            raise BadRequest("after_occurrences cannot be negative")
        snapshot = dict(order.reminder_rules_snapshot or {})
        snapshot["escalation"] = {"after_occurrences": after_occurrences}
        snapshot["escalated"] = False
        order.reminder_rules_snapshot = snapshot
        db.session.commit()
        AuditService.log_event(current_user.tenant_id, current_user.id, "reminder_escalation_configured", title="הוגדרה הסלמה לתזכורת", metadata={"order_id": order.id, "after_occurrences": after_occurrences})
        db.session.commit()
        return jsonify({"success": True, "order": order.to_dict()})
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "invalid_escalation"}), 400
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, BadRequest):
            return jsonify({"success": False, "error": "bad_request", "message": exc.description}), 400
        if isinstance(exc, NotFound):
            return jsonify({"success": False, "error": "not_found", "message": exc.description}), 404
        raise
