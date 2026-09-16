from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, VALID_MOVEMENT_TYPES
from app.models.product import Product
from app.services.inventory_planning_service import InventoryPlanningService

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


@inventory_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    products = db.session.scalars(
        select(Product)
        .where(Product.tenant_id == current_user.tenant_id, Product.active.is_(True))
        .order_by(Product.name.asc())
    ).all()
    product_ids = [p.id for p in products]
    movements = []
    if product_ids:
        movements = db.session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == current_user.tenant_id,
                InventoryMovement.product_id.in_(product_ids),
            )
            .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
            .limit(500)
        ).all()

    low_stock = [p for p in products if p.min_stock is not None and (p.current_stock or 0) <= p.min_stock]
    out_of_stock = [p for p in products if (p.current_stock or 0) <= 0]
    no_stock_rule = [p for p in products if p.min_stock is None and p.recommended_stock is None]
    return jsonify({
        "success": True,
        "stats": {
            "active_products": len(products),
            "low_stock": len(low_stock),
            "out_of_stock": len(out_of_stock),
            "without_stock_rule": len(no_stock_rule),
            "movement_count": len(movements),
        },
        "products": [p.to_dict() for p in products],
        "recent_movements": [m.to_dict() for m in movements[:50]],
    })


@inventory_bp.route("/movements", methods=["GET"])
@login_required
def list_movements():
    product_id = request.args.get("product_id", type=int)
    movement_type = (request.args.get("movement_type") or "").strip().lower()
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    if movement_type and movement_type not in VALID_MOVEMENT_TYPES:
        return _handle(BadRequest("movement_type is invalid"))

    statement = select(InventoryMovement).where(InventoryMovement.tenant_id == current_user.tenant_id)
    if product_id is not None:
        statement = statement.where(InventoryMovement.product_id == product_id)
    if movement_type:
        statement = statement.where(InventoryMovement.movement_type == movement_type)
    rows = db.session.scalars(
        statement.order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc()).limit(limit)
    ).all()
    return jsonify({"success": True, "movements": [row.to_dict() for row in rows]})


@inventory_bp.route("/products/<int:product_id>/movements", methods=["GET"])
@login_required
def product_movements(product_id):
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    product = db.session.scalar(
        select(Product).where(Product.id == product_id, Product.tenant_id == current_user.tenant_id)
    )
    if product is None:
        from werkzeug.exceptions import NotFound
        return _handle(NotFound("Product not found"))
    rows = db.session.scalars(
        select(InventoryMovement)
        .where(
            InventoryMovement.tenant_id == current_user.tenant_id,
            InventoryMovement.product_id == product_id,
        )
        .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
        .limit(limit)
    ).all()
    return jsonify({"success": True, "product": product.to_dict(), "movements": [row.to_dict() for row in rows]})


@inventory_bp.route("/movements", methods=["POST"])
@login_required
def create_movement():
    payload = request.get_json(silent=True) or {}
    product_id = payload.get("product_id")
    movement_type = str(payload.get("movement_type") or "").strip().lower()
    quantity = payload.get("quantity")
    if not product_id or not movement_type or quantity is None:
        return _handle(BadRequest("product_id, movement_type and quantity are required"))
    if movement_type not in VALID_MOVEMENT_TYPES:
        return _handle(BadRequest("movement_type is invalid"))

    try:
        occurred_at = None
        raw_occurred_at = payload.get("occurred_at")
        if raw_occurred_at:
            occurred_at = datetime.fromisoformat(str(raw_occurred_at).replace("Z", "+00:00"))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        movement = InventoryPlanningService(current_user.tenant_id).record_movement(
            product_id=product_id,
            movement_type=movement_type,
            quantity=quantity,
            user_id=current_user.id,
            reference_type=payload.get("reference_type"),
            reference_id=payload.get("reference_id"),
            note=str(payload.get("note") or "").strip() or None,
            occurred_at=occurred_at,
        )
        db.session.commit()
        return jsonify({"success": True, "movement": movement.to_dict()}), 201
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except Exception:
        db.session.rollback()
        raise
