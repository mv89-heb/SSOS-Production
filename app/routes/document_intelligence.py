import os
import uuid

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException

from app.services.document_intelligence_service import DocumentIntelligenceService


document_intelligence_bp = Blueprint(
    "document_intelligence", __name__, url_prefix="/api/document-intelligence"
)


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


@document_intelligence_bp.route("/upload", methods=["POST"])
@login_required
def upload_document():
    try:
        if "file" not in request.files:
            raise BadRequest("file is required")
        upload = request.files["file"]
        if not upload.filename:
            raise BadRequest("file is required")
        ext = os.path.splitext(upload.filename)[1].lower()
        allowed = DocumentIntelligenceService.ALLOWED_EXTENSIONS
        if ext not in allowed or upload.mimetype not in DocumentIntelligenceService.ALLOWED_MIMES:
            raise BadRequest("Only PDF and PNG/JPEG/WEBP documents are supported")

        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size <= 0:
            raise BadRequest("Uploaded document is empty")
        if size > current_app.config["MAX_CONTENT_LENGTH"]:
            raise BadRequest("Uploaded document exceeds the maximum allowed size")

        unique_name = f"{uuid.uuid4().hex}{ext}"
        directory = os.path.join(current_app.config["UPLOAD_FOLDER"], "documents")
        os.makedirs(directory, exist_ok=True)
        storage_path = os.path.join(directory, unique_name)
        upload.save(storage_path)

        service = DocumentIntelligenceService(current_user.tenant_id, current_user.id)
        row = service.create_analysis(upload.filename, storage_path, upload.mimetype)
        return jsonify({"success": True, "analysis": row.to_dict()}), 201
    except HTTPException as exc:
        return _handle(exc)


@document_intelligence_bp.route("/<int:analysis_id>/analyze", methods=["POST"])
@login_required
def analyze_document(analysis_id):
    try:
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).analyze(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()})
    except HTTPException as exc:
        return _handle(exc)


@document_intelligence_bp.route("/<int:analysis_id>", methods=["GET"])
@login_required
def get_document_analysis(analysis_id):
    try:
        row = DocumentIntelligenceService(current_user.tenant_id, current_user.id).get(analysis_id)
        return jsonify({"success": True, "analysis": row.to_dict()})
    except HTTPException as exc:
        return _handle(exc)
