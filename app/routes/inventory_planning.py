from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound
from sqlalchemy import select

from app.extensions import db
from app.models.inventory_planning_period import InventoryPlanningPeriod
from app.models.inventory_consumption_profile import InventoryConsumptionProfile
from app.models.product import Product
from app.models.supplier import Supplier
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
            limit=request.args.get("limit", default=2000, type=int),
        )
        return jsonify({"success": True, "recommendations": rows})
    except (ValueError, TypeError) as exc:
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        return _handle(exc)



def _profile_decimal(payload, key, current=None, minimum=Decimal("0")):
    value = payload.get(key, current)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise BadRequest(f"{key} must be a number")
    if not parsed.is_finite() or parsed < minimum:
        raise BadRequest(f"{key} must be at least {minimum}")
    return parsed


def _profile_ids(payload, key, model):
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        raise BadRequest(f"{key} must be an array")
    try:
        ids = list(dict.fromkeys(int(value) for value in raw))
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must contain numeric IDs")
    if len(ids) > 200 or any(value <= 0 for value in ids):
        raise BadRequest(f"{key} contains invalid IDs")
    if not ids:
        return []
    rows = db.session.scalars(select(model).where(
        model.tenant_id == current_user.tenant_id,
        model.id.in_(ids),
        model.active.is_(True),
    )).all()
    if len(rows) != len(ids):
        raise BadRequest(f"{key} contains records outside this organization or inactive records")
    return ids


def _serialize_profile(profile):
    supplier_rows = db.session.scalars(select(Supplier).where(
        Supplier.tenant_id == current_user.tenant_id,
        Supplier.id.in_(profile.supplier_ids or []),
    )).all() if profile.supplier_ids else []
    product_rows = db.session.scalars(select(Product).where(
        Product.tenant_id == current_user.tenant_id,
        Product.id.in_(profile.product_ids or []),
    )).all() if profile.product_ids else []
    return profile.to_dict(
        suppliers={row.id: row.name for row in supplier_rows},
        products={row.id: row.name for row in product_rows},
    )


@inventory_planning_bp.route("/profiles/options", methods=["GET"])
@login_required
def consumption_profile_options():
    suppliers = db.session.scalars(select(Supplier).where(
        Supplier.tenant_id == current_user.tenant_id, Supplier.active.is_(True)
    ).order_by(Supplier.name)).all()
    products = db.session.scalars(select(Product).where(
        Product.tenant_id == current_user.tenant_id, Product.active.is_(True)
    ).order_by(Product.name)).all()
    return jsonify({
        "success": True,
        "suppliers": [{"id": row.id, "name": row.name} for row in suppliers],
        "products": [{"id": row.id, "name": row.name, "supplier_id": row.supplier_id, "unit": row.unit} for row in products],
    })


@inventory_planning_bp.route("/profiles", methods=["GET"])
@login_required
def list_consumption_profiles():
    rows = db.session.scalars(select(InventoryConsumptionProfile).where(
        InventoryConsumptionProfile.tenant_id == current_user.tenant_id,
        InventoryConsumptionProfile.active.is_(True),
    ).order_by(InventoryConsumptionProfile.category, InventoryConsumptionProfile.name)).all()
    return jsonify({"success": True, "profiles": [_serialize_profile(row) for row in rows]})


@inventory_planning_bp.route("/profiles", methods=["POST"])
@login_required
def create_consumption_profile():
    try:
        _require_manager()
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        category = str(payload.get("category") or "").strip()
        if not name or not category:
            raise BadRequest("name and category are required")
        duplicate = db.session.scalar(select(InventoryConsumptionProfile.id).where(
            InventoryConsumptionProfile.tenant_id == current_user.tenant_id,
            InventoryConsumptionProfile.name == name,
        ))
        if duplicate:
            raise BadRequest("A consumption profile with this name already exists")
        supplier_ids = _profile_ids(payload, "supplier_ids", Supplier)
        product_ids = _profile_ids(payload, "product_ids", Product)
        if product_ids:
            linked_products = db.session.scalars(select(Product).where(
                Product.tenant_id == current_user.tenant_id, Product.id.in_(product_ids)
            )).all()
            if any(row.supplier_id not in supplier_ids for row in linked_products):
                raise BadRequest("Every linked product must belong to one of the selected suppliers")
        profile = InventoryConsumptionProfile(
            tenant_id=current_user.tenant_id, name=name, category=category,
            supplier_ids=supplier_ids, product_ids=product_ids,
            min_order_quantity=_profile_decimal(payload, "min_order_quantity"),
            max_order_quantity=_profile_decimal(payload, "max_order_quantity"),
            average_order_quantity=_profile_decimal(payload, "average_order_quantity"),
            regular_weekly_consumption=_profile_decimal(payload, "regular_weekly_consumption"),
            reinforced_weekly_consumption=_profile_decimal(payload, "reinforced_weekly_consumption"),
            reinforcement_cycle_weeks=_profile_decimal(payload, "reinforcement_cycle_weeks", minimum=Decimal("1")),
            safety_stock=_profile_decimal(payload, "safety_stock"),
            order_status=str(payload.get("order_status") or "healthy"),
            source_note=str(payload.get("source_note") or "").strip() or None,
            created_by=current_user.id, updated_by=current_user.id,
            active=True,
        )
        if profile.order_status not in ("healthy", "reorder"):
            raise BadRequest("order_status must be healthy or reorder")
        if profile.max_order_quantity < profile.min_order_quantity:
            raise BadRequest("max_order_quantity must be greater than or equal to min_order_quantity")
        db.session.add(profile)
        db.session.commit()
        return jsonify({"success": True, "profile": _serialize_profile(profile)}), 201
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/profiles/<int:profile_id>", methods=["PUT"])
@login_required
def update_consumption_profile(profile_id):
    try:
        _require_manager()
        profile = db.session.scalar(select(InventoryConsumptionProfile).where(
            InventoryConsumptionProfile.id == profile_id,
            InventoryConsumptionProfile.tenant_id == current_user.tenant_id,
        ))
        if profile is None:
            raise NotFound("Consumption profile not found")
        payload = request.get_json(silent=True) or {}
        if "name" in payload:
            profile.name = str(payload.get("name") or "").strip()
        if "category" in payload:
            profile.category = str(payload.get("category") or "").strip()
        if not profile.name or not profile.category:
            raise BadRequest("name and category are required")
        duplicate = db.session.scalar(select(InventoryConsumptionProfile.id).where(
            InventoryConsumptionProfile.tenant_id == current_user.tenant_id,
            InventoryConsumptionProfile.name == profile.name,
            InventoryConsumptionProfile.id != profile.id,
        ))
        if duplicate:
            raise BadRequest("A consumption profile with this name already exists")
        if "supplier_ids" in payload:
            profile.supplier_ids = _profile_ids(payload, "supplier_ids", Supplier)
        if "product_ids" in payload:
            profile.product_ids = _profile_ids(payload, "product_ids", Product)
        linked_products = db.session.scalars(select(Product).where(
            Product.tenant_id == current_user.tenant_id,
            Product.id.in_(profile.product_ids or []),
        )).all() if profile.product_ids else []
        if any(row.supplier_id not in (profile.supplier_ids or []) for row in linked_products):
            raise BadRequest("Every linked product must belong to one of the selected suppliers")
        fields = {
            "min_order_quantity": Decimal("0"),
            "max_order_quantity": Decimal("0"),
            "average_order_quantity": Decimal("0"),
            "regular_weekly_consumption": Decimal("0"),
            "reinforced_weekly_consumption": Decimal("0"),
            "reinforcement_cycle_weeks": Decimal("1"),
            "safety_stock": Decimal("0"),
        }
        for key, minimum in fields.items():
            if key in payload:
                setattr(profile, key, _profile_decimal(payload, key, minimum=minimum))
        if profile.max_order_quantity < profile.min_order_quantity:
            raise BadRequest("max_order_quantity must be greater than or equal to min_order_quantity")
        if "order_status" in payload:
            status = str(payload.get("order_status") or "")
            if status not in ("healthy", "reorder"):
                raise BadRequest("order_status must be healthy or reorder")
            profile.order_status = status
        if "source_note" in payload:
            profile.source_note = str(payload.get("source_note") or "").strip() or None
        profile.updated_by = current_user.id
        db.session.commit()
        return jsonify({"success": True, "profile": _serialize_profile(profile)})
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@inventory_planning_bp.route("/profiles/<int:profile_id>", methods=["DELETE"])
@login_required
def archive_consumption_profile(profile_id):
    try:
        _require_manager()
        profile = db.session.scalar(select(InventoryConsumptionProfile).where(
            InventoryConsumptionProfile.id == profile_id,
            InventoryConsumptionProfile.tenant_id == current_user.tenant_id,
        ))
        if profile is None:
            raise NotFound("Consumption profile not found")
        profile.active = False
        db.session.commit()
        return jsonify({"success": True})
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
