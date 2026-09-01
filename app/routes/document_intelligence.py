import os, uuid
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException
from app.services.document_intelligence_service import DocumentIntelligenceService
document_intelligence_bp=Blueprint("document_intelligence",__name__,url_prefix="/api/document-intelligence")
def _handle(exc): return jsonify({"success":False,"error":exc.name.lower().replace(" ","_"),"message":exc.description}),exc.code
@document_intelligence_bp.route("/upload",methods=["POST"])
@login_required
def upload_document():
    try:
        if "file" not in request.files or not request.files["file"].filename: raise BadRequest("file is required")
        upload=request.files["file"]; ext=os.path.splitext(upload.filename)[1].lower()
        if ext not in DocumentIntelligenceService.ALLOWED_EXTENSIONS or upload.mimetype not in DocumentIntelligenceService.ALLOWED_MIMES: raise BadRequest("Only PDF and PNG/JPEG/WEBP documents are supported")
        upload.stream.seek(0,os.SEEK_END); size=upload.stream.tell(); upload.stream.seek(0)
        if size<=0: raise BadRequest("Uploaded document is empty")
        if size>current_app.config["MAX_CONTENT_LENGTH"]: raise BadRequest("Uploaded document exceeds the maximum allowed size")
        directory=os.path.join(current_app.config["UPLOAD_FOLDER"],"documents"); os.makedirs(directory,exist_ok=True)
        storage_path=os.path.join(directory,f"{uuid.uuid4().hex}{ext}"); upload.save(storage_path)
        row=DocumentIntelligenceService(current_user.tenant_id,current_user.id).create_analysis(upload.filename,storage_path,upload.mimetype)
        return jsonify({"success":True,"analysis":row.to_dict()}),201
    except HTTPException as exc: return _handle(exc)
@document_intelligence_bp.route("/<int:analysis_id>/analyze",methods=["POST"])
@login_required
def analyze_document(analysis_id):
    try: return jsonify({"success":True,"analysis":DocumentIntelligenceService(current_user.tenant_id,current_user.id).analyze(analysis_id).to_dict()})
    except HTTPException as exc: return _handle(exc)
@document_intelligence_bp.route("/<int:analysis_id>",methods=["GET"])
@login_required
def get_document_analysis(analysis_id):
    try: return jsonify({"success":True,"analysis":DocumentIntelligenceService(current_user.tenant_id,current_user.id).get(analysis_id).to_dict()})
    except HTTPException as exc: return _handle(exc)
