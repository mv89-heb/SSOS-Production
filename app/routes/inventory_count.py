from datetime import datetime, timezone
from uuid import uuid4
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, Conflict, HTTPException

from app.extensions import db
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.services.inventory_planning_service import InventoryPlanningService
from app.services.permission_service import PermissionService

inventory_count_bp = Blueprint("inventory_count", __name__, url_prefix="/api/inventory/count")

def _handle(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code

def _latest_count_query(tenant_id):
    return (
        select(InventoryMovement)
        .where(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.movement_type == "count",
        )
        .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
    )

@inventory_count_bp.route("/latest", methods=["GET"])
@login_required
def latest_count():
    try:
        PermissionService.require_permission("inventory.view")
    except HTTPException as exc:
        return _handle(exc)

    latest = db.session.scalars(_latest_count_query(current_user.tenant_id).limit(1)).first()
    if latest is None:
        return jsonify({"success": True, "has_count": False, "count_id": None, "counted_at": None, "counted": 0, "movements": []})

    count_id = latest.reference_id if latest.reference_type == "bulk_inventory_count" and latest.reference_id else None
    if count_id:
        movements = db.session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == current_user.tenant_id,
                InventoryMovement.movement_type == "count",
                InventoryMovement.reference_type == "bulk_inventory_count",
                InventoryMovement.reference_id == count_id,
            )
            .order_by(InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
    else:
        # Legacy records have no session key. Return one latest row per product
        # from that day, rather than only one product or repeated saves.
        from datetime import timedelta
        day_start = latest.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        raw_movements = db.session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.tenant_id == current_user.tenant_id,
                InventoryMovement.movement_type == "count",
                InventoryMovement.occurred_at >= day_start,
                InventoryMovement.occurred_at < day_end,
            ).order_by(InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
        ).all()
        latest_by_product = {}
        for movement in raw_movements:
            previous = latest_by_product.get(movement.product_id)
            if previous is None or (movement.occurred_at, movement.id) > (previous.occurred_at, previous.id):
                latest_by_product[movement.product_id] = movement
        movements = sorted(latest_by_product.values(), key=lambda m: (m.occurred_at, m.id))

    return jsonify({
        "success": True,
        "has_count": True,
        "count_id": count_id,
        "counted_at": latest.occurred_at.isoformat() if latest.occurred_at else None,
        "counted": len(movements),
        "note": latest.note,
        "movements": [movement.to_dict() for movement in movements],
    })

@inventory_count_bp.route("/bulk", methods=["POST"])
@login_required
def bulk_count():
    try:
        PermissionService.require_permission("inventory.count")
    except HTTPException as exc:
        return _handle(exc)

    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return _handle(BadRequest("items must be a non-empty list"))
    if len(items) > 2000:
        return _handle(BadRequest("Too many products in one count"))
    note = str(payload.get("note") or "").strip() or None
    occurred_at = None
    raw_occurred_at = payload.get("occurred_at")
    if raw_occurred_at:
        try:
            occurred_at = datetime.fromisoformat(str(raw_occurred_at).replace("Z", "+00:00"))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return _handle(BadRequest("occurred_at must be a valid ISO date"))

    normalized = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            return _handle(BadRequest("Each item must be an object"))
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
            return _handle(BadRequest("product_id must be a positive integer"))
        if product_id in seen:
            return _handle(BadRequest("Duplicate product_id: %s" % product_id))
        seen.add(product_id)
        try:
            quantity_value = int(quantity)
        except (TypeError, ValueError):
            return _handle(BadRequest("Invalid quantity for product %s" % product_id))
        if quantity_value < 0:
            return _handle(BadRequest("Quantity cannot be negative for product %s" % product_id))
        normalized.append((product_id, quantity_value))

    service = InventoryPlanningService(current_user.tenant_id)
    movements = []
    count_id = str(payload.get("count_id") or "").strip() or uuid4().hex
    if len(count_id) > 100:
        return _handle(BadRequest("count_id must not exceed 100 characters"))

    # A retried bulk count must never reset stock to a stale snapshot after
    # later inventory movements. Treat count_id as an idempotency token.
    existing = db.session.scalars(
        select(InventoryMovement)
        .where(
            InventoryMovement.tenant_id == current_user.tenant_id,
            InventoryMovement.movement_type == "count",
            InventoryMovement.reference_type == "bulk_inventory_count",
            InventoryMovement.reference_id == count_id,
        )
        .order_by(InventoryMovement.id.asc())
        ).all()
        if existing:
        existing_quantities = {
            movement.product_id: int(movement.quantity) for movement in existing
        }
        requested_quantities = dict(normalized)
        same_note = all((movement.note or None) == note for movement in existing)
        if existing_quantities != requested_quantities or not same_note:
            return _handle(Conflict("count_id was already used for a different inventory count"))
        existing_payload = [movement.to_dict() for movement in existing]
        return jsonify({
            "success": True,
            "count_id": count_id,
            "counted": len(existing_payload),
            "counted_at": existing_payload[-1]["occurred_at"] if existing_payload else None,
            "movements": existing_payload,
            "replayed": True,
        }), 200

    try:
        for product_id, quantity in normalized:
            movement = service.record_movement(
                product_id=product_id,
                movement_type="count",
                quantity=quantity,
                user_id=current_user.id,
                reference_type="bulk_inventory_count",
                reference_id=count_id,
                note=note,
                occurred_at=occurred_at,
            )
            movements.append(movement.to_dict())
        db.session.commit()
    except (ValueError, TypeError, HTTPException) as exc:
        db.session.rollback()
        if isinstance(exc, HTTPException):
            return _handle(exc)
        return _handle(BadRequest(str(exc)))
    except Exception:
        db.session.rollback()
        raise
    counted_at = movements[-1]["occurred_at"] if movements else None
    return jsonify({"success": True, "count_id": count_id, "counted": len(movements), "counted_at": counted_at, "movements": movements})
