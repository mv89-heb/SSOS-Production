from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from app.extensions import db
from app.models.order import REMINDER_COMPLETE, REMINDER_PENDING, Order
from app.repositories.base_repository import BaseRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.order_reminder_service import OrderReminderService

order_reminders_bp = Blueprint(
    "order_reminders", __name__, url_prefix="/api/order-reminders"
)


class OrderReminderRepository(BaseRepository):
    model = Order

    def list_open(self, user_id: int | None = None):
        stmt = self._tenant_select().where(Order.reminder_state != REMINDER_COMPLETE)
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        stmt = stmt.order_by(Order.next_reminder_at.asc().nullslast(), Order.id.asc())
        return list(db.session.execute(stmt).scalars().all())


def _json_error(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


def _get_owned_open_order(order_id: int):
    repo = OrderReminderRepository(tenant_id=current_user.tenant_id)
    order = repo.get_by_id_for_update(order_id)
    if order is None or order.user_id != current_user.id:
        raise NotFound("Order not found")
    if order.status in ("sent", "completed", "cancelled"):
        raise BadRequest("Reminder cannot be changed for a closed order")
    return order


def _get_supplier_rules(order: Order):
    suppliers = SupplierRepository(tenant_id=current_user.tenant_id).get_all_for_matching()
    matching = next((item for item in suppliers if item.name == order.supplier_name), None)
    return matching.ordering_rules if matching else None


@order_reminders_bp.route("/suppliers/<int:supplier_id>", methods=["POST"])
@login_required
def set_supplier_rules(supplier_id: int):
    """Persist normalized supplier ordering/reminder windows."""
    supplier = SupplierRepository(tenant_id=current_user.tenant_id).get_by_id_or_404(supplier_id)
    data = request.get_json(silent=True) or {}
    try:
        if "windows" in data:
            rules = {
                "windows": data["windows"],
                "remind_minutes_before_close": data.get(
                    "remind_minutes_before_close", OrderReminderService.DEFAULT_MINUTES
                ),
            }
            OrderReminderService.windows_from_rules(rules)
        else:
            days = data.get("order_days", [])
            rules = OrderReminderService.build_rules(
                order_days=days,
                opens_at=data.get("opens_at", "08:00"),
                closes_at=data.get("closes_at", "16:00"),
                remind_minutes_before_close=data.get("remind_minutes_before_close"),
            )
    except (TypeError, ValueError, KeyError) as exc:
        return _json_error(BadRequest(str(exc)))

    supplier.ordering_rules = rules
    db.session.commit()
    return jsonify({"success": True, "supplier": supplier.to_dict()})


@order_reminders_bp.route("/preview", methods=["POST"])
@login_required
def preview():
    """Preview reminder points for a supplier without changing state."""
    data = request.get_json(silent=True) or {}
    rules = data.get("rules")
    if not isinstance(rules, dict):
        return _json_error(BadRequest("rules must be an object"))
    raw_now = data.get("now")
    try:
        now = datetime.fromisoformat(raw_now.replace("Z", "+00:00")) if raw_now else datetime.now(timezone.utc)
        points = OrderReminderService.plan_reminders(now, rules)
    except (TypeError, ValueError, KeyError) as exc:
        return _json_error(BadRequest(str(exc)))
    return jsonify({
        "success": True,
        "reminders": [
            {"at": point.at.isoformat(), "level": point.level, "label": point.label}
            for point in points
        ],
    })


@order_reminders_bp.route("", methods=["GET"])
@login_required
def list_open_reminders():
    repo = OrderReminderRepository(tenant_id=current_user.tenant_id)
    orders = repo.list_open(user_id=current_user.id)
    return jsonify({
        "success": True,
        "reminders": [
            {
                "order": order.to_dict(),
                "next_reminder_at": order.next_reminder_at.isoformat() if order.next_reminder_at else None,
            }
            for order in orders
        ],
    })


@order_reminders_bp.route("/orders/<int:order_id>/configuration", methods=["GET"])
@login_required
def reminder_configuration(order_id: int):
    """Return whether this order can use automatic supplier-based reminders."""
    try:
        order = _get_owned_open_order(order_id)
    except HTTPException as exc:
        return _json_error(exc)
    rules = _get_supplier_rules(order)
    return jsonify({
        "success": True,
        "has_supplier_rules": bool(rules),
        "supplier_name": order.supplier_name,
    })


@order_reminders_bp.route("/orders/<int:order_id>/activate", methods=["POST"])
@login_required
def activate_order_reminder(order_id: int):
    """Activate automatic reminders, or create a safe one-off fallback when rules are absent."""
    repo = OrderReminderRepository(tenant_id=current_user.tenant_id)
    order = repo.get_by_id_for_update(order_id)
    if order is None:
        return _json_error(NotFound("Order not found"))
    if order.user_id != current_user.id:
        return _json_error(NotFound("Order not found"))
    if order.status in ("sent", "completed", "cancelled"):
        return _json_error(BadRequest("Reminder cannot be activated for a closed order"))

    rules = _get_supplier_rules(order)
    now = datetime.now(timezone.utc)
    if rules:
        points = OrderReminderService.plan_reminders(now, rules)
        order.reminder_rules_snapshot = rules
        order.next_reminder_at = points[0].at if points else None
        order.reminder_state = REMINDER_PENDING if points else REMINDER_COMPLETE
    else:
        # No ordering/delivery calendar exists, so there is no honest automatic
        # date to calculate. Keep the user's explicit activation useful by
        # creating a one-off reminder one hour from now. It can then be snoozed,
        # completed, or replaced by supplier rules later.
        order.reminder_rules_snapshot = {
            "mode": "manual_fallback",
            "note": "נוצרה תזכורת חד-פעמית כי לספק אין ימי הזמנה/אספקה מוגדרים.",
            "created_at": now.isoformat(),
        }
        order.next_reminder_at = now + timedelta(hours=1)
        order.reminder_state = REMINDER_PENDING

    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@order_reminders_bp.route("/orders/<int:order_id>/manual", methods=["POST"])
@login_required
def create_manual_order_reminder(order_id: int):
    """Create a one-off reminder when supplier scheduling rules are unavailable."""
    try:
        order = _get_owned_open_order(order_id)
        data = request.get_json(silent=True) or {}
        raw_at = data.get("reminder_at")
        if not raw_at or not isinstance(raw_at, str):
            raise BadRequest("reminder_at is required")
        reminder_at = datetime.fromisoformat(raw_at.replace("Z", "+00:00"))
        if reminder_at.tzinfo is None:
            reminder_at = reminder_at.replace(tzinfo=timezone.utc)
        reminder_at = reminder_at.astimezone(timezone.utc)
        if reminder_at <= datetime.now(timezone.utc):
            raise BadRequest("reminder_at must be in the future")
        note = str(data.get("note") or "").strip()
        if len(note) > 500:
            raise BadRequest("note must be 500 characters or fewer")
    except (TypeError, ValueError) as exc:
        return _json_error(BadRequest(f"Invalid reminder date: {exc}"))
    except HTTPException as exc:
        return _json_error(exc)

    order.reminder_rules_snapshot = {
        "mode": "manual",
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    order.next_reminder_at = reminder_at
    order.reminder_state = REMINDER_PENDING
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@order_reminders_bp.route("/orders/<int:order_id>/complete", methods=["POST"])
@login_required
def complete_order_reminder(order_id: int):
    """Dismiss the current follow-up reminder without changing order status."""
    try:
        order = _get_owned_open_order(order_id)
    except HTTPException as exc:
        return _json_error(exc)
    order.reminder_state = REMINDER_COMPLETE
    order.next_reminder_at = None
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})


@order_reminders_bp.route("/orders/<int:order_id>/snooze", methods=["POST"])
@login_required
def snooze_order_reminder(order_id: int):
    """Move the current reminder forward by a caller-selected number of minutes."""
    try:
        order = _get_owned_open_order(order_id)
        data = request.get_json(silent=True) or {}
        minutes = int(data.get("minutes", 60))
        if minutes < 5 or minutes > 10080:
            raise BadRequest("minutes must be between 5 and 10080")
    except (ValueError, TypeError):
        return _json_error(BadRequest("minutes must be an integer"))
    except HTTPException as exc:
        return _json_error(exc)

    base = order.next_reminder_at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    order.next_reminder_at = max(base, datetime.now(timezone.utc)) + timedelta(minutes=minutes)
    order.reminder_state = REMINDER_PENDING
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})
