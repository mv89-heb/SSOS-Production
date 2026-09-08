from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from app.extensions import db
from app.models.order import REMINDER_COMPLETE, REMINDER_PENDING, Order
from app.repositories.base_repository import BaseRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.order_reminder_service import OrderReminderService
from app.services.reminder_ai_service import ReminderAIService
from app.services import google_calendar_service as gcal

order_reminders_bp = Blueprint("order_reminders", __name__, url_prefix="/api/order-reminders")


class OrderReminderRepository(BaseRepository):
    model = Order

    def list_open(self, user_id: int | None = None):
        stmt = self._tenant_select().where(Order.reminder_state != REMINDER_COMPLETE)
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        stmt = stmt.order_by(Order.next_reminder_at.asc().nullslast(), Order.id.asc())
        return list(db.session.execute(stmt).scalars().all())


def _json_error(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _unexpected_error(message: str, exc: Exception, stage: str | None = None):
    request_id = request.headers.get("Rndr-Id")
    current_app.logger.exception("%s stage=%s order_id=%s request_id=%s", message, stage or "unknown", request.view_args.get("order_id") if request.view_args else None, request_id or "unknown", exc_info=exc)
    try:
        db.session.rollback()
    except Exception:
        current_app.logger.exception("Reminder transaction rollback failed")
    return jsonify({"success": False, "error": "internal_server_error", "message": "אירעה שגיאה בהפעלת התזכורת. נסה שוב.", "request_id": request_id}), 500


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
    target = (order.supplier_name or "").strip().casefold()
    matching = next((item for item in suppliers if (item.name or "").strip().casefold() == target), None)
    return matching.ordering_rules if matching else None


def _fallback_candidates(now: datetime):
    timezone_name = current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem")
    try:
        local_zone = ZoneInfo(timezone_name)
    except Exception:
        local_zone = timezone.utc
    local_now = (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).astimezone(local_zone)
    tomorrow = local_now + timedelta(days=1)
    day_after = local_now + timedelta(days=2)
    return [
        {"at": (local_now + timedelta(hours=1)).isoformat(), "label": "מעקב בעוד שעה", "level": "upcoming"},
        {"at": tomorrow.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(), "label": "מעקב מחר בבוקר", "level": "upcoming"},
        {"at": day_after.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(), "label": "מעקב בעוד יומיים", "level": "upcoming"},
    ]


def _refresh_order_after_calendar_failure(order: Order):
    try:
        db.session.refresh(order)
    except Exception:
        current_app.logger.exception("Failed to refresh order after calendar failure")


def _sync_google_calendar(order: Order) -> str | None:
    try:
        event_id = gcal.sync_order_event(order)
        if event_id:
            db.session.commit()
        return event_id
    except Exception:
        current_app.logger.exception("Google Calendar reminder sync failed; reminder remains persisted")
        db.session.rollback()
        _refresh_order_after_calendar_failure(order)
        return None


def _delete_google_calendar_event(order: Order) -> bool:
    try:
        gcal.delete_order_event(order)
        db.session.commit()
        return True
    except Exception:
        current_app.logger.exception("Google Calendar reminder deletion failed; reminder completion remains persisted")
        db.session.rollback()
        _refresh_order_after_calendar_failure(order)
        return False


@order_reminders_bp.route("/suppliers/<int:supplier_id>", methods=["POST"])
@login_required
def set_supplier_rules(supplier_id: int):
    supplier = SupplierRepository(tenant_id=current_user.tenant_id).get_by_id_or_404(supplier_id)
    data = request.get_json(silent=True) or {}
    try:
        if "windows" in data:
            rules = {"windows": data["windows"], "remind_minutes_before_close": data.get("remind_minutes_before_close", OrderReminderService.DEFAULT_MINUTES)}
            OrderReminderService.windows_from_rules(rules)
        else:
            rules = OrderReminderService.build_rules(order_days=data.get("order_days", []), opens_at=data.get("opens_at", "08:00"), closes_at=data.get("closes_at", "16:00"), remind_minutes_before_close=data.get("remind_minutes_before_close"), timezone_name=data.get("timezone", current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem")))
    except (TypeError, ValueError, KeyError) as exc:
        return _json_error(BadRequest(str(exc)))
    supplier.ordering_rules = rules
    db.session.commit()
    return jsonify({"success": True, "supplier": supplier.to_dict()})


@order_reminders_bp.route("/preview", methods=["POST"])
@login_required
def preview():
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
    return jsonify({"success": True, "reminders": [{"at": point.at.isoformat(), "level": point.level, "label": point.label} for point in points]})


@order_reminders_bp.route("", methods=["GET"])
@login_required
def list_open_reminders():
    orders = OrderReminderRepository(tenant_id=current_user.tenant_id).list_open(user_id=current_user.id)
    return jsonify({"success": True, "reminders": [{"order": order.to_dict(), "next_reminder_at": order.next_reminder_at.isoformat() if order.next_reminder_at else None} for order in orders]})


@order_reminders_bp.route("/orders/<int:order_id>/configuration", methods=["GET"])
@login_required
def reminder_configuration(order_id: int):
    try:
        order = _get_owned_open_order(order_id)
        rules = _get_supplier_rules(order)
        connection = gcal.get_connection(current_user.id, current_user.tenant_id)
        return jsonify({"success": True, "has_supplier_rules": bool(rules), "supplier_name": order.supplier_name, "google_calendar_connected": bool(connection)})
    except HTTPException as exc:
        return _json_error(exc)
    except Exception as exc:
        return _unexpected_error("Reminder configuration lookup failed", exc, "configuration")


@order_reminders_bp.route("/orders/<int:order_id>/ai-analysis", methods=["POST"])
@login_required
def analyze_order_reminder_with_ai(order_id: int):
    try:
        order = _get_owned_open_order(order_id)
        data = request.get_json(silent=True) or {}
        user_text = str(data.get("text") or data.get("note") or "").strip()
        raw_deadline = data.get("deadline")
        deadline = None
        if raw_deadline:
            deadline = datetime.fromisoformat(str(raw_deadline).replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        analysis = ReminderAIService.analyze(order, user_text=user_text, deadline=deadline)
        return jsonify({"success": True, "ai": analysis, "display": ReminderAIService.urgency_display(analysis["urgency"])})
    except (TypeError, ValueError) as exc:
        return _json_error(BadRequest(str(exc)))
    except HTTPException as exc:
        return _json_error(exc)
    except Exception as exc:
        return _unexpected_error("AI reminder analysis failed", exc, "ai_analysis")


@order_reminders_bp.route("/orders/<int:order_id>/natural-language", methods=["POST"])
@login_required
def natural_language_order_reminder(order_id: int):
    try:
        order = _get_owned_open_order(order_id)
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        if not text:
            raise BadRequest("text is required")
        analysis = ReminderAIService.parse_natural_language(order, text)
        apply = bool(data.get("apply", False))
        calendar_event_id = None
        if apply:
            reminder_at = datetime.fromisoformat(analysis["first_reminder_at"])
            ReminderAIService.apply_analysis(order, analysis, reminder_at=reminder_at, mode="natural_language_ai")
            order.reminder_state = REMINDER_PENDING
            db.session.commit()
            calendar_event_id = _sync_google_calendar(order)
        return jsonify({"success": True, "applied": apply, "ai": analysis, "display": ReminderAIService.urgency_display(analysis["urgency"]), "order": order.to_dict() if apply else None, "calendar_event_id": calendar_event_id})
    except (TypeError, ValueError) as exc:
        return _json_error(BadRequest(str(exc)))
    except HTTPException as exc:
        return _json_error(exc)
    except Exception as exc:
        return _unexpected_error("Natural language reminder failed", exc, "natural_language")


@order_reminders_bp.route("/orders/<int:order_id>/activate", methods=["POST"])
@login_required
def activate_order_reminder(order_id: int):
    stage = "load_order"
    try:
        repo = OrderReminderRepository(tenant_id=current_user.tenant_id)
        order = repo.get_by_id_for_update(order_id)
        if order is None or order.user_id != current_user.id:
            return _json_error(NotFound("Order not found"))
        if order.status in ("sent", "completed", "cancelled"):
            return _json_error(BadRequest("Reminder cannot be activated for a closed order"))

        stage = "load_supplier_rules"
        rules = _get_supplier_rules(order)
        now = datetime.now(timezone.utc)
        chosen = None
        ai_reason = None

        if rules:
            stage = "plan_reminders"
            points = OrderReminderService.plan_reminders(now, rules)
            candidates = [{"at": point.at.isoformat(), "level": point.level, "label": point.label} for point in points]
            if not candidates:
                candidates = _fallback_candidates(now)
                mode = "supplier_rules_fallback"
                fallback_note = "כללי הספק לא יצרו מועד עתידי, ולכן נבחר מועד גיבוי."
            else:
                mode = "supplier_rules"
                fallback_note = None
        else:
            candidates = _fallback_candidates(now)
            mode = "manual_fallback"
            fallback_note = "נוצרה תזכורת כי לספק אין ימי הזמנה/אספקה מוגדרים."

        stage = "choose_candidate"
        chosen = ReminderAIService.choose_candidate(order, candidates, now)
        chosen_at = chosen.get("at") if chosen else candidates[0]["at"]
        ai_reason = chosen.get("reason") if chosen else fallback_note or "נבחר מועד המעקב הראשון לפי כללי הספק."

        stage = "ai_urgency"
        analysis = ReminderAIService.analyze(order, now=now, user_text=order.notes or "")

        stage = "persist_reminder"
        next_at = datetime.fromisoformat(chosen_at)
        if next_at.tzinfo is None:
            next_at = next_at.replace(tzinfo=timezone.utc)
        ReminderAIService.apply_analysis(order, analysis, reminder_at=next_at.astimezone(timezone.utc), mode=mode)
        snapshot = dict(order.reminder_rules_snapshot or {})
        snapshot["supplier_rules"] = rules if rules else None
        snapshot["candidate_reason"] = ai_reason
        snapshot["fallback_note"] = fallback_note
        order.reminder_rules_snapshot = snapshot
        order.reminder_state = REMINDER_PENDING
        db.session.commit()

        stage = "google_calendar"
        calendar_event_id = _sync_google_calendar(order)
        return jsonify({"success": True, "order": order.to_dict(), "calendar_event_id": calendar_event_id, "ai": analysis, "ai_reason": ai_reason})
    except HTTPException as exc:
        return _json_error(exc)
    except Exception as exc:
        return _unexpected_error("Reminder activation failed", exc, stage)


@order_reminders_bp.route("/orders/<int:order_id>/manual", methods=["POST"])
@login_required
def create_manual_order_reminder(order_id: int):
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
    try:
        analysis = ReminderAIService.analyze(order, user_text=note) if note else ReminderAIService.analyze(order)
        ReminderAIService.apply_analysis(order, analysis, reminder_at=reminder_at, mode="manual_ai")
        snapshot = dict(order.reminder_rules_snapshot or {})
        snapshot["note"] = note
        order.reminder_rules_snapshot = snapshot
        order.reminder_state = REMINDER_PENDING
        db.session.commit()
        calendar_event_id = _sync_google_calendar(order)
        return jsonify({"success": True, "order": order.to_dict(), "calendar_event_id": calendar_event_id, "ai": analysis})
    except Exception as exc:
        return _unexpected_error("Manual reminder creation failed", exc, "manual")


@order_reminders_bp.route("/orders/<int:order_id>/complete", methods=["POST"])
@login_required
def complete_order_reminder(order_id: int):
    try:
        order = _get_owned_open_order(order_id)
    except HTTPException as exc:
        return _json_error(exc)
    try:
        order.reminder_state = REMINDER_COMPLETE
        order.next_reminder_at = None
        db.session.commit()
        _delete_google_calendar_event(order)
        return jsonify({"success": True, "order": order.to_dict()})
    except Exception as exc:
        return _unexpected_error("Completing reminder failed", exc, "complete")


@order_reminders_bp.route("/orders/<int:order_id>/snooze", methods=["POST"])
@login_required
def snooze_order_reminder(order_id: int):
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
    try:
        base = order.next_reminder_at or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        order.next_reminder_at = max(base, datetime.now(timezone.utc)) + timedelta(minutes=minutes)
        order.reminder_state = REMINDER_PENDING
        db.session.commit()
        calendar_event_id = _sync_google_calendar(order)
        return jsonify({"success": True, "order": order.to_dict(), "calendar_event_id": calendar_event_id})
    except Exception as exc:
        return _unexpected_error("Snoozing reminder failed", exc, "snooze")
