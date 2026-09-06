from datetime import datetime, timezone

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


@order_reminders_bp.route("/orders/<int:order_id>/activate", methods=["POST"])
@login_required
def activate_order_reminder(order_id: int):
    """Snapshot supplier reminder rules onto an order and plan its next alert."""
    repo = OrderReminderRepository(tenant_id=current_user.tenant_id)
    order = repo.get_by_id_for_update(order_id)
    if order is None:
        return _json_error(NotFound("Order not found"))
    if order.user_id != current_user.id:
        return _json_error(NotFound("Order not found"))
    if order.status in ("sent", "completed", "cancelled"):
        return _json_error(BadRequest("Reminder cannot be activated for a closed order"))
    supplier = SupplierRepository(tenant_id=current_user.tenant_id).get_all_for_matching()
    matching = next((item for item in supplier if item.name == order.supplier_name), None)
    if matching is None or not matching.ordering_rules:
        return _json_error(BadRequest("Supplier has no ordering rules configured"))

    now = datetime.now(timezone.utc)
    points = OrderReminderService.plan_reminders(now, matching.ordering_rules)
    order.reminder_rules_snapshot = matching.ordering_rules
    order.next_reminder_at = points[0].at if points else None
    order.reminder_state = REMINDER_PENDING if points else REMINDER_COMPLETE
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})
