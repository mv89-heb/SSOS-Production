from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException

from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("", methods=["GET"])
@login_required
def list_audit_logs():
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code

    limit = min(int(request.args.get("limit", 100)), 500)
    offset = max(int(request.args.get("offset", 0)), 0)

    repo = AuditRepository(tenant_id=current_user.tenant_id)
    logs = repo.list_all(limit=limit, offset=offset)
    return jsonify({"success": True, "logs": [log.to_dict() for log in logs]})


@audit_bp.route("/verify", methods=["GET"])
@login_required
def verify_audit_chain():
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code

    is_valid, broken_id = AuditService.verify_chain(current_user.tenant_id)
    return jsonify({"success": True, "valid": is_valid, "first_broken_log_id": broken_id})
