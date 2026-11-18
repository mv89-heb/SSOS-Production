from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException, BadRequest, NotFound

from app.extensions import db
from app.models.order import Order
from app.models.user import ROLE_MANAGER
from app.services.permission_service import PermissionService
from app.services.procurement_budget_service import ProcurementBudgetService


procurement_budgets_bp = Blueprint(
    "procurement_budgets", __name__, url_prefix="/api/procurement-budgets"
)


def _service():
    return ProcurementBudgetService(current_user.tenant_id)


def _handle(exc):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


@procurement_budgets_bp.route("", methods=["GET"])
@login_required
def list_procurement_budgets():
    try:
        PermissionService.require_permission("orders.view")
        return jsonify({"success": True, "budgets": _service().list_budgets()}), 200
    except HTTPException as exc:
        return _handle(exc)


@procurement_budgets_bp.route("", methods=["POST"])
@login_required
def create_procurement_budget():
    try:
        PermissionService.require_role_at_least(ROLE_MANAGER)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise BadRequest("Budget payload must be an object")
        budget = _service().create_budget(current_user, payload)
        db.session.commit()
        return jsonify({"success": True, "budget": budget}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@procurement_budgets_bp.route("/<int:budget_id>", methods=["PUT"])
@login_required
def update_procurement_budget(budget_id):
    try:
        PermissionService.require_role_at_least(ROLE_MANAGER)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise BadRequest("Budget payload must be an object")
        budget = _service().update_budget(current_user, budget_id, payload)
        db.session.commit()
        return jsonify({"success": True, "budget": budget}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@procurement_budgets_bp.route("/<int:budget_id>", methods=["DELETE"])
@login_required
def deactivate_procurement_budget(budget_id):
    try:
        PermissionService.require_role_at_least(ROLE_MANAGER)
        budget = _service().deactivate_budget(current_user, budget_id)
        db.session.commit()
        return jsonify({"success": True, "budget": budget}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)


@procurement_budgets_bp.route("/orders/<int:order_id>/impact", methods=["GET"])
@login_required
def get_order_budget_impact(order_id):
    try:
        PermissionService.require_permission("orders.view")
        order = Order.query.filter_by(id=order_id, tenant_id=current_user.tenant_id).first()
        if order is None:
            raise NotFound("Order not found")
        return jsonify({
            "success": True,
            "budget_impact": _service().preview_order(order),
        }), 200
    except HTTPException as exc:
        return _handle(exc)
