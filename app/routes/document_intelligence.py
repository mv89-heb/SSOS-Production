import logging
import os
import tempfile

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db

from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.permission_service import PermissionService


document_intelligence_bp = Blueprint("document_intelligence", __name__, url_prefix="/api/document-intelligence")
logger = logging.getLogger(__name__)


def _handle(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _internal_error(exc, operation):
    db.session.rollback()
    logger.exception("Document intelligence %s failed", operation)
    return jsonify({
        "success": False,
        "error": "internal_error",
        "message": f"Document intelligence {operation} failed. Check backend logs for details.",
    }), 500


def _delete_file(path):
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        logger.warning("Could not delete temporary document %s", path, exc_info=True)


@document_intelligence_bp.route("/upload", methods=["POST"])
@login_required
def upload_document():
    storage_path = None
    try:
        PermissionService.require_permission("documents.upload")
        if "file" not in request.files or not request.files["file"].filename:
            raise BadRequest("file is required")
        upload = request.files["file"]
        ext = os.path.splitext(upload.filename)[1].lower()
        mime_type = (upload.mimetype or "").lower()

        if ext not in DocumentIntelligenceService.ALLOWED_EXTENSIONS:
            raise BadRequest("Unsupported document extension")
        # Some browsers/proxies report SVG as application/octet-stream. SVG is
        # validated by extension and is always stored with image/svg+xml.
        if ext == ".svg":
            if mime_type not in {"image/svg+xml", "application/octet-stream", "text/xml", "application/xml", ""}:
                raise BadRequest("Invalid SVG MIME type")
            mime_type = "image/svg+xml"
        elif mime_type not in DocumentIntelligenceService.ALLOWED_MIMES:
            raise BadRequest("Unsupported document MIME type")

        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        max_size = current_app.config.get("MAX_CONTENT_LENGTH")
        if size <= 0:
            raise BadRequest("Uploaded document is empty")
        if max_size is not None and size > max_size:
            raise BadRequest("Uploaded document exceeds the maximum allowed size")

        # Render instances have an ephemeral filesystem. Stage the document in
        # the OS temp directory so it survives the upload request and is
        # available to the explicit /analyze request. The analysis service
        # deletes it after processing succeeds or fails.
        fd, storage_path = tempfile.mkstemp(prefix="ssos-document-", suffix=ext)
        os.close(fd)
        upload.save(storage_path)
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).create_analysis(
            upload.filename, storage_path, mime_type
        )
        # Do not delete storage_path here: the client analyzes this staged row
        # in a subsequent request. The service owns cleanup after analysis.
        storage_path = None
        return jsonify({"success": True, "analysis": row.to_dict()}), 201
    except HTTPException as exc:
        _delete_file(storage_path)
        return _handle(exc)
    except Exception as exc:
        _delete_file(storage_path)
        return _internal_error(exc, "upload")


@document_intelligence_bp.route("/<int:analysis_id>/analyze", methods=["POST"])
@login_required
def analyze_document(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).analyze(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()})
    except HTTPException as exc:
        return _handle(exc)
    except Exception as exc:
        return _internal_error(exc, "analysis")


@document_intelligence_bp.route("/<int:analysis_id>/rematch", methods=["POST"])
@login_required
def rematch_document(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).rematch(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()}), 200
    except HTTPException as exc:
        return _handle(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "message": str(exc)}), 400
    except Exception as exc:
        return _internal_error(exc, "rematch")


@document_intelligence_bp.route("/<int:analysis_id>/compare-order", methods=["POST"])
@login_required
def compare_document_with_order(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        payload = request.get_json(silent=True) or {}
        order_id = payload.get("order_id")
        if not isinstance(order_id, int) or isinstance(order_id, bool) or order_id <= 0:
            raise BadRequest("A valid order_id is required")
        confirm_supplier = payload.get("confirm_supplier") is True
        row, reconciliation = DocumentIntelligenceService(
            current_user.tenant_id, current_user.id
        ).compare_with_order(analysis_id, order_id, confirm_supplier=confirm_supplier)
        return jsonify({"success": True, "analysis": row.to_dict(), "reconciliation": reconciliation}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except Exception as exc:
        return _internal_error(exc, "order reconciliation")


@document_intelligence_bp.route("/<int:analysis_id>/apply", methods=["POST"])
@login_required
def apply_document(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        payload = request.get_json(silent=True) or {}
        lines = payload.get("lines")
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).apply(analysis_id, lines)
        return jsonify({"success": True, "analysis": row.to_dict()}), 200
    except HTTPException as exc:
        return _handle(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "message": str(exc)}), 400
    except Exception as exc:
        return _internal_error(exc, "apply")


@document_intelligence_bp.route("/<int:analysis_id>/apply-delivery-note", methods=["POST"])
@login_required
def apply_scanned_delivery_note(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        row, receipt = DocumentIntelligenceService(
            current_user.tenant_id, current_user.id
        ).apply_delivery_note(analysis_id, current_user)
        return jsonify({
            "success": True, "analysis": row.to_dict(), "receipt": receipt.to_dict(),
        }), 201
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "message": str(exc)}), 400
    except Exception as exc:
        return _internal_error(exc, "delivery note reconciliation")


@document_intelligence_bp.route("/<int:analysis_id>/apply-invoice", methods=["POST"])
@login_required
def apply_scanned_invoice(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        payload = request.get_json(silent=True) or {}
        row, invoice, updated_prices = DocumentIntelligenceService(
            current_user.tenant_id, current_user.id
        ).apply_invoice_reconciliation(analysis_id, payload)
        return jsonify({
            "success": True, "analysis": row.to_dict(), "invoice": invoice.to_dict(),
            "automatic_price_updates": updated_prices,
        }), 201
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": "validation_error", "message": str(exc)}), 400
    except Exception as exc:
        return _internal_error(exc, "invoice reconciliation")


@document_intelligence_bp.route("/<int:analysis_id>/create-product", methods=["POST"])
@login_required
def create_product_from_document_line(analysis_id):
    try:
        PermissionService.require_permission("documents.process")
        payload = request.get_json(silent=True) or {}
        line_index = payload.get("line_index")
        if not isinstance(line_index, int) or isinstance(line_index, bool):
            raise BadRequest("line_index is required")
        product_data = payload.get("product") if isinstance(payload.get("product"), dict) else {}
        row, product = DocumentIntelligenceService(
            current_user.tenant_id, current_user.id
        ).create_product_from_line(analysis_id, line_index, product_data)
        return jsonify({"success": True, "analysis": row.to_dict(), "product": product.to_dict()}), 201
    except HTTPException as exc:
        return _handle(exc)
    except Exception as exc:
        return _internal_error(exc, "create-product")


@document_intelligence_bp.route("/<int:analysis_id>", methods=["GET"])
@login_required
def get_document_analysis(analysis_id):
    try:
        PermissionService.require_permission("documents.view")
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).get(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()}), 200
    except HTTPException as exc:
        return _handle(exc)
    except Exception as exc:
        return _internal_error(exc, "get")
