from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException

from app.services.bulk_price_update_service import BulkPriceUpdateService, BulkPriceUpdateError
from app.services.permission_service import PermissionService

bulk_price_update_bp = Blueprint(
    "bulk_price_update",
    __name__,
    url_prefix="/api/imports",
)


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


@bulk_price_update_bp.route("/<int:session_id>/price-update/preview", methods=["GET"])
@login_required
def price_update_preview(session_id):
    """Preview only existing-product price changes; never mutates the catalog."""
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = BulkPriceUpdateService(current_user.tenant_id, current_user.id)
    try:
        preview = service.preview(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except BulkPriceUpdateError as exc:
        return jsonify({"success": False, "error": "price_update_blocked", "message": str(exc)}), 422

    return jsonify({"success": True, "preview": preview})


@bulk_price_update_bp.route("/<int:session_id>/price-update/commit", methods=["POST"])
@login_required
def commit_price_update(session_id):
    """Commit only matched existing-product price changes from the validated file."""
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = BulkPriceUpdateService(current_user.tenant_id, current_user.id)
    try:
        execution = service.commit(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except BulkPriceUpdateError as exc:
        return jsonify({"success": False, "error": "price_update_failed", "message": str(exc)}), 422

    from app.extensions import db
    db.session.commit()
    return jsonify({
        "success": True,
        "mode": "PRICE_UPDATE_ONLY",
        "execution": execution.to_dict(),
    }), 201
