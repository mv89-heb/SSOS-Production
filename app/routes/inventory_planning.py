from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound
from sqlalchemy import select

from app.extensions import db
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.services.inventory_calendar_service import InventoryCalendarService
from app.services.permission_service import PermissionService

inventory_planning_bp = Blueprint("inventory_planning", __name__, url_prefix="/api/inventory/planning")


def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _parse_date(value, field):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise BadRequest(f"{field} must be YYYY-MM-DD")


def _require_manager():
    PermissionService.require_role_at_least("manager")


@inventory_planning_bp.route("/periods", methods=["GET"])
@login_required
def list_periods():
    service = InventoryCalendarService(current_user.tenant_id)
    rows = service.periods(active_only=request.args.get("active_only", "true").lower() != "false")
    return jsonify({"success": True, "periods": [row.to_dict() for row in rows]})


@inventory_planning_bp.route("/periods", methods=["POST"])
@login_required
def create_period():
    try:
        _require_manager()
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            raise BadRequest("name is required")
        start_date = _parse_date(payload.get("start_date"), "start_date")
        end_date = _parse_date(payload.get("end_date"), "end_date")
        if end_date < start_date:
            raise BadRequest("end_date must be on or after start_date")
        multiplier = float(payload.get("consumption_multiplier", 1))
        if multiplier <= 0 or multiplier > 10:
            raise BadRequest("consumption_multiplier must be between 0.01 and 10")
        period = InventoryPlanningPeriod(
            tenant_id=current_user.tenant_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            consumption_multiplier=multiplier,
            order_days=str(payload.get("order_days") or "").strip() or None,
            delivery_days=str(payload.get("delivery_days") or "").strip() or None,
            order_cutoff_time=str(payload.get("order_cutoff_time") or "").strip() or None,
            active=bool(payload.get("active", True)),
            notes=str(payload.get("notes") or "").strip() or None,
            created_by=current_user.id,
        )
        db.session.add(period)
        db.session.commit()
        return jsonify({"success": True, "period": period.to_dict()}), 201
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/periods/<int:period_id>", methods=["PUT"])
@login_required
def update_period(period_id):
    try:
        _require_manager()
        period = db.session.scalar(select(InventoryPlanningPeriod).where(InventoryPlanningPeriod.id == period_id, InventoryPlanningPeriod.tenant_id == current_user.tenant_id))
        if period is None:
            raise NotFound("Planning period not found")
        payload = request.get_json(silent=True) or {}
        if "name" in payload:
            period.name = str(payload.get("name") or "").strip()
        if "start_date" in payload:
            period.start_date = _parse_date(payload.get("start_date"), "start_date")
        if "end_date" in payload:
            period.end_date = _parse_date(payload.get("end_date"), "end_date")
        if period.end_date < period.start_date:
            raise BadRequest("end_date must be on or after start_date")
        if "consumption_multiplier" in payload:
            multiplier = float(payload.get("consumption_multiplier"))
            if multiplier <= 0 or multiplier > 10:
                raise BadRequest("consumption_multiplier must be between 0.01 and 10")
            period.consumption_multiplier = multiplier
        for field in ("order_days", "delivery_days", "order_cutoff_time", "notes"):
            if field in payload:
                setattr(period, field, str(payload.get(field) or "").strip() or None)
        if "active" in payload:
            period.active = bool(payload.get("active"))
        db.session.commit()
        return jsonify({"success": True, "period": period.to_dict()})
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/periods/<int:period_id>", methods=["DELETE"])
@login_required
def delete_period(period_id):
    try:
        _require_manager()
        period = db.session.scalar(select(InventoryPlanningPeriod).where(InventoryPlanningPeriod.id == period_id, InventoryPlanningPeriod.tenant_id == current_user.tenant_id))
        if period is None:
            raise NotFound("Planning period not found")
        db.session.delete(period)
        db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/seed-holidays", methods=["POST"])
@login_required
def seed_holidays():
    """Seed editable major Jewish holiday periods for the current and next year."""
    try:
        _require_manager()
        suggested = [
            ("פסח", date(2026, 4, 1), date(2026, 4, 8)),
            ("שבועות", date(2026, 5, 21), date(2026, 5, 22)),
            ("ראש השנה", date(2026, 9, 11), date(2026, 9, 13)),
            ("יום כיפור", date(2026, 9, 20), date(2026, 9, 21)),
            ("סוכות ושמיני עצרת", date(2026, 9, 25), date(2026, 10, 3)),
            ("פסח", date(2027, 4, 21), date(2027, 4, 28)),
            ("שבועות", date(2027, 6, 10), date(2027, 6, 11)),
            ("ראש השנה", date(2027, 10, 1), date(2027, 10, 3)),
            ("יום כיפור", date(2027, 10, 10), date(2027, 10, 11)),
            ("סוכות ושמיני עצרת", date(2027, 10, 15), date(2027, 10, 23)),
        ]
        created = []
        for name, start_date, end_date in suggested:
            exists = db.session.scalar(
                select(InventoryPlanningPeriod).where(
                    InventoryPlanningPeriod.tenant_id == current_user.tenant_id,
                    InventoryPlanningPeriod.name == name,
                    InventoryPlanningPeriod.start_date == start_date,
                    InventoryPlanningPeriod.end_date == end_date,
                )
            )
            if exists:
                continue
            period = InventoryPlanningPeriod(
                tenant_id=current_user.tenant_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                consumption_multiplier=InventoryCalendarService.DEFAULT_HOLIDAY_MULTIPLIER,
                active=True,
                notes="נוצר אוטומטית כתקופת חג מומלצת. יש להתאים את מכפיל הצריכה ואת ימי ההזמנה/אספקה למציאות בארגון.",
                created_by=current_user.id,
            )
            db.session.add(period)
            created.append(period)
        db.session.commit()
        return jsonify({"success": True, "created_count": len(created), "periods": [row.to_dict() for row in created]})
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/count-status", methods=["GET"])
@login_required
def count_status():
    return jsonify({"success": True, **InventoryCalendarService(current_user.tenant_id).count_status()})


@inventory_planning_bp.route("/recommendations", methods=["GET"])
@login_required
def recommendations():
    try:
        service = InventoryCalendarService(current_user.tenant_id)
        rows = service.recommendations(
            lookback_days=request.args.get("lookback_days", default=60, type=int),
            safety_days=request.args.get("safety_days", default=2, type=int),
            limit=request.args.get("limit", default=500, type=int),
        )
        return jsonify({"success": True, "recommendations": rows})
    except (ValueError, TypeError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)
