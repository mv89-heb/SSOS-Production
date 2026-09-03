import logging
import os
import tempfile
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException

from app.services.document_intelligence_service import DocumentIntelligenceService


document_intelligence_bp = Blueprint("document_intelligence", __name__, url_prefix="/api/document-intelligence")
logger = logging.getLogger(__name__)


def _handle(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _internal_error(exc, operation):
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
        # the OS temp directory rather than inside the application tree. The
        # file exists only long enough for the analysis flow and is deleted on
        # every exit path.
        fd, storage_path = tempfile.mkstemp(prefix="ssos-document-", suffix=ext)
        os.close(fd)
        upload.save(storage_path)
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).create_analysis(
            upload.filename, storage_path, mime_type
        )
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
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).analyze(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()})
    except HTTPException as exc:
        return _handle(exc)
    except Exception as exc:
        # Never expose an unhandled Flask 500 for provider/filesystem/runtime
        # failures. The detailed traceback remains in the backend logs.
        return _internal_error(exc, "analysis")


@document_intelligence_bp.route("/<int:analysis_id>/apply", methods=["POST"])
@login_required
def apply_document(analysis_id):
    try:
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


@document_intelligence_bp.route("/<int:analysis_id>", methods=["GET"])
@login_required
def get_document_analysis(analysis_id):
    try:
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).get(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()}), 200
    except HTTPException as exc:
        return _handle(exc)
    except Exception as exc:
        return _internal_error(exc, "get")
