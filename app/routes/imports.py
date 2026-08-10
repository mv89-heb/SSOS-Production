import os
import uuid

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException

from app.extensions import db
from app.services.import_service import ImportService
from app.services.import_analysis_service import ImportAnalysisService, ImportAnalysisError
from app.services.import_mapping_service import ImportMappingService, ImportMappingError
from app.services.import_validation_service import ImportValidationService, ImportValidationError
from app.services.import_execution_service import ImportExecutionService, ImportExecutionError
from app.services.permission_service import PermissionService

imports_bp = Blueprint("imports", __name__, url_prefix="/api/imports")


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


def _validate_import_upload(filename: str, mime_type: str, file_size: int) -> str | None:
    """Returns an error message if the upload is invalid, else None.
    Mirrors the OCR upload's validate_upload() pattern but for spreadsheet
    types instead of images/PDF (see app/config.py IMPORT_UPLOAD_*)."""
    if not filename:
        return "No filename provided"

    ext = os.path.splitext(filename)[1].lower()
    if ext not in current_app.config["IMPORT_UPLOAD_EXTENSIONS"]:
        allowed = ", ".join(sorted(current_app.config["IMPORT_UPLOAD_EXTENSIONS"]))
        return f"Unsupported file extension: {ext}. Allowed: {allowed}"

    if mime_type not in current_app.config["IMPORT_UPLOAD_MIME_TYPES"]:
        return f"Unsupported MIME type: {mime_type}"

    if file_size > current_app.config["MAX_CONTENT_LENGTH"]:
        return f"File exceeds maximum allowed size of {current_app.config['MAX_CONTENT_LENGTH']} bytes"

    return None


@imports_bp.route("", methods=["GET"])
@login_required
def list_sessions():
    """
    List recent import sessions for the current tenant.
    ---
    tags:
      - Imports
    responses:
      200:
        description: List of import sessions
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportService(current_user.tenant_id, current_user.id)
    sessions = service.list_sessions()
    return jsonify({"success": True, "sessions": [s.to_dict(include_headers=False) for s in sessions]})


@imports_bp.route("/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    """
    Get one import session's status/metadata.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Import session detail
      404:
        description: Session not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportService(current_user.tenant_id, current_user.id)
    try:
        session = service.get_session(session_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "session": session.to_dict()})


@imports_bp.route("/<int:session_id>/rows", methods=["GET"])
@login_required
def get_session_rows(session_id):
    """
    Get the raw, unmodified rows staged for one import session (paginated).
    This is Phase 3.1 scope only — rows are shown exactly as parsed, with
    no mapping or validation applied yet.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
      - name: limit
        in: query
        type: integer
        default: 100
      - name: offset
        in: query
        type: integer
        default: 0
    responses:
      200:
        description: Raw rows for the session
      404:
        description: Session not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    limit = min(request.args.get("limit", 100, type=int) or 100, 500)
    offset = max(request.args.get("offset", 0, type=int) or 0, 0)

    service = ImportService(current_user.tenant_id, current_user.id)
    try:
        rows = service.get_session_rows(session_id, limit=limit, offset=offset)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "rows": [r.to_dict() for r in rows]})


@imports_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    """
    Upload a supplier price list (Excel or CSV) and stage it as raw rows.
    Nothing is written to products/suppliers/offers by this endpoint —
    see ImportService for the staging-only guarantee.
    ---
    tags:
      - Imports
    parameters:
      - name: file
        in: formData
        type: file
        required: true
      - name: supplier_id
        in: formData
        type: integer
        required: false
        description: Set only if the whole file is a single supplier's price list.
      - name: sheet_name
        in: formData
        type: string
        required: false
        description: Which worksheet to read for .xlsx/.xls (defaults to the first sheet).
    responses:
      201:
        description: Import session created (check its status — parsing failures are
          reported as status=FAILED with error_message, not as an HTTP error)
      400:
        description: Invalid upload (missing file, wrong type, too large)
      404:
        description: supplier_id given but not found in this tenant
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    if "file" not in request.files:
        return jsonify({"success": False, "error": "no_file"}), 400

    upload_file = request.files["file"]
    if not upload_file.filename:
        return jsonify({"success": False, "error": "no_file"}), 400

    filename = upload_file.filename
    mime_type = upload_file.mimetype

    upload_file.stream.seek(0, os.SEEK_END)
    file_size = upload_file.stream.tell()
    upload_file.stream.seek(0)

    validation_error = _validate_import_upload(filename, mime_type, file_size)
    if validation_error:
        return jsonify({"success": False, "error": "invalid_upload", "message": validation_error}), 400

    supplier_id = request.form.get("supplier_id", type=int)
    sheet_name = request.form.get("sheet_name") or None

    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "imports", unique_name)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    upload_file.save(save_path)

    service = ImportService(current_user.tenant_id, current_user.id)
    try:
        session = service.create_session_and_parse(
            filename=filename, storage_path=save_path, supplier_id=supplier_id, sheet_name=sheet_name,
        )
    except HTTPException as exc:
        return _handle(exc)

    db.session.commit()
    return jsonify({"success": True, "session": session.to_dict()}), 201


# ------------------------------------------------------------------------
# Phase 3.2A: Import Analysis Engine — read-only structural analysis
# ------------------------------------------------------------------------

@imports_bp.route("/<int:session_id>/analyze", methods=["POST"])
@login_required
def analyze_session(session_id):
    """
    Analyze an uploaded workbook's structure: sheets, header shape,
    wide/tall orientation, per-column type guesses, detected suppliers/
    units, and data-quality issues. Read-only against the originally
    uploaded file — never creates/updates a Product, Supplier, or
    SupplierProductOffer. Safe to call again; replaces previous findings
    for this session rather than accumulating them.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Analysis complete
      404:
        description: Session not found
      422:
        description: The original file could not be read for analysis
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportAnalysisService(current_user.tenant_id, current_user.id)
    try:
        analyses = service.analyze(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportAnalysisError as exc:
        return jsonify({"success": False, "error": "analysis_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "analysis": [a.to_dict() for a in analyses]})


@imports_bp.route("/<int:session_id>/analysis", methods=["GET"])
@login_required
def get_analysis(session_id):
    """
    Get the most recent structural analysis for an import session (see
    POST .../analyze). Empty list if analysis hasn't been run yet.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Analysis results (possibly empty, if not yet analyzed)
      404:
        description: Session not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportAnalysisService(current_user.tenant_id, current_user.id)
    try:
        analyses = service.get_analysis(session_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "analysis": [a.to_dict() for a in analyses]})


# ------------------------------------------------------------------------
# Phase 3.2B: Mapping Engine — suggest, review, approve column mappings
# ------------------------------------------------------------------------

@imports_bp.route("/<int:session_id>/mapping", methods=["GET"])
@login_required
def get_mapping(session_id):
    """
    Get (creating on first call) the mapping workspace for this session's
    staged sheet: every column with the engine's suggestion plus whatever
    decisions have already been saved. Still writes nothing to
    products/suppliers/supplier_product_offers.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Mapping workspace (mapping + matching_templates)
      404:
        description: Session not found
      422:
        description: Session has no staged sheet to map yet
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        mapping, templates = service.get_or_create_mapping(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportMappingError as exc:
        return jsonify({"success": False, "error": "mapping_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({
        "success": True,
        "mapping": mapping.to_dict(),
        "matching_templates": [t.to_dict() for t in templates],
    })


@imports_bp.route("/<int:session_id>/mapping", methods=["POST"])
@login_required
def update_mapping(session_id):
    """
    Save column mapping decisions (confirm or override the engine's
    suggestions). Body: {"decisions": [{"column_index", "target",
    "supplier_id"?, "supplier_name"?, "price_type"?}, ...]}.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            decisions:
              type: array
              items:
                type: object
    responses:
      200:
        description: Updated mapping
      400:
        description: Invalid decision
      404:
        description: Session or mapping not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    decisions = data.get("decisions", [])

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        mapping, _ = service.get_or_create_mapping(session_id)
        mapping = service.update_columns(mapping.id, decisions)
    except HTTPException as exc:
        return _handle(exc)
    except ImportMappingError as exc:
        return jsonify({"success": False, "error": "mapping_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "mapping": mapping.to_dict()})


@imports_bp.route("/<int:session_id>/mapping/approve", methods=["POST"])
@login_required
def approve_mapping(session_id):
    """
    Mark this session's mapping as reviewed and approved — a person has
    confirmed how every column should be interpreted. Still creates
    nothing in the catalog; that's a later phase (Import Execution).
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Approved mapping
      404:
        description: Session or mapping not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        mapping, _ = service.get_or_create_mapping(session_id)
        mapping = service.approve_mapping(mapping.id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportMappingError as exc:
        return jsonify({"success": False, "error": "mapping_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "mapping": mapping.to_dict()})


@imports_bp.route("/<int:session_id>/mapping/templates", methods=["GET"])
@login_required
def list_mapping_templates(session_id):
    """
    List all saved mapping templates for this tenant (not scoped to this
    session — templates are reusable across sessions/suppliers).
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: List of templates
      404:
        description: Session not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        service.session_repo.get_by_id_or_404(session_id)
    except HTTPException as exc:
        return _handle(exc)
    templates = service.list_templates()
    return jsonify({"success": True, "templates": [t.to_dict() for t in templates]})


@imports_bp.route("/<int:session_id>/mapping/templates", methods=["POST"])
@login_required
def save_mapping_template(session_id):
    """
    Save this session's current mapping decisions as a reusable template.
    Body: {"name": str, "supplier_id"?: int}.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          required: [name]
          properties:
            name:
              type: string
            supplier_id:
              type: integer
    responses:
      201:
        description: Template created
      400:
        description: Missing name
      404:
        description: Session, mapping, or supplier not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "name_required", "message": "Template name is required."}), 400

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        mapping, _ = service.get_or_create_mapping(session_id)
        template = service.save_template(mapping.id, name, supplier_id=data.get("supplier_id"))
    except HTTPException as exc:
        return _handle(exc)
    except ImportMappingError as exc:
        return jsonify({"success": False, "error": "mapping_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "template": template.to_dict()}), 201


@imports_bp.route("/<int:session_id>/mapping/templates/<int:template_id>/apply", methods=["POST"])
@login_required
def apply_mapping_template(session_id, template_id):
    """
    Apply a saved template's decisions to this session's mapping, matched
    by column header text. Still fully editable afterward — this only
    pre-fills, it doesn't lock anything in.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
      - name: template_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Mapping updated from template
      404:
        description: Session, mapping, or template not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportMappingService(current_user.tenant_id, current_user.id)
    try:
        mapping, _ = service.get_or_create_mapping(session_id)
        mapping = service.apply_template(mapping.id, template_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportMappingError as exc:
        return jsonify({"success": False, "error": "mapping_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "mapping": mapping.to_dict()})


# ------------------------------------------------------------------------
# Phase 3.2C: Validation & Import Preview Engine
# ------------------------------------------------------------------------

@imports_bp.route("/<int:session_id>/validate", methods=["POST"])
@login_required
def validate_session(session_id):
    """
    Run validation: interpret every raw row through the APPROVED mapping,
    check against the real catalog for duplicates, and compute what WOULD
    happen. Requires an approved mapping. Still writes nothing to
    products/suppliers/supplier_product_offers.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Validation complete
      404:
        description: Session not found
      422:
        description: No mapping yet, or mapping not approved
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportValidationService(current_user.tenant_id, current_user.id)
    try:
        validation = service.validate(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportValidationError as exc:
        return jsonify({"success": False, "error": "validation_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "validation": validation.to_dict()})


@imports_bp.route("/<int:session_id>/validation", methods=["GET"])
@login_required
def get_validation(session_id):
    """
    Get the most recent validation run's summary and issues (error/warning
    list). 404 if validation hasn't been run yet.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Validation summary + issues
      404:
        description: Session not found, or no validation has been run yet
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportValidationService(current_user.tenant_id, current_user.id)
    try:
        validation = service.get_latest_validation(session_id)
    except HTTPException as exc:
        return _handle(exc)
    if validation is None:
        return jsonify({"success": False, "error": "not_found", "message": "No validation has been run for this session yet."}), 404

    data = validation.to_dict()
    data["issues"] = [i.to_dict() for i in validation.issues]
    return jsonify({"success": True, "validation": data})


@imports_bp.route("/<int:session_id>/preview", methods=["GET"])
@login_required
def get_preview(session_id):
    """
    Get the per-row preview table (detail view) for the most recent
    validation run: what each row would become. 404 if validation hasn't
    been run yet.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
      - name: limit
        in: query
        type: integer
        default: 200
      - name: offset
        in: query
        type: integer
        default: 0
    responses:
      200:
        description: Per-row preview
      404:
        description: Session not found, or no validation has been run yet
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    limit = min(request.args.get("limit", 200, type=int) or 200, 500)
    offset = max(request.args.get("offset", 0, type=int) or 0, 0)

    service = ImportValidationService(current_user.tenant_id, current_user.id)
    try:
        validation = service.get_latest_validation(session_id)
    except HTTPException as exc:
        return _handle(exc)
    if validation is None:
        return jsonify({"success": False, "error": "not_found", "message": "No validation has been run for this session yet."}), 404

    rows = service.preview_repo.get_by_validation(validation.id, limit=limit, offset=offset)
    return jsonify({
        "success": True,
        "validation_id": validation.id,
        "summary": validation.to_dict()["summary"],
        "rows": [r.to_dict() for r in rows],
    })


# ------------------------------------------------------------------------
# Phase 3.2D-MVP: Import Execution Engine — commit an approved, validated
# preview to the real catalog. Every write goes through CatalogService.
# ------------------------------------------------------------------------

@imports_bp.route("/<int:session_id>/commit", methods=["POST"])
@login_required
def commit_import(session_id):
    """
    Commit this session's latest validated preview to the real catalog:
    creates missing suppliers, creates/updates products, creates
    alternate-supplier offers. Requires an approved mapping and a
    completed validation. All-or-nothing — see ImportExecutionService.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      201:
        description: Import committed
      404:
        description: Session not found
      422:
        description: Not ready to commit (mapping not approved, not validated,
          or already committed)
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportExecutionService(current_user.tenant_id, current_user.id)
    try:
        execution = service.commit(session_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportExecutionError as exc:
        return jsonify({"success": False, "error": "commit_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "execution": execution.to_dict()}), 201


@imports_bp.route("/<int:session_id>/execution", methods=["GET"])
@login_required
def get_execution(session_id):
    """
    Get the most recent import execution (commit) for this session.
    ---
    tags:
      - Imports
    parameters:
      - name: session_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Execution record
      404:
        description: Session not found, or nothing has been committed yet
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportExecutionService(current_user.tenant_id, current_user.id)
    try:
        execution = service.get_latest_execution(session_id)
    except HTTPException as exc:
        return _handle(exc)
    if execution is None:
        return jsonify({"success": False, "error": "not_found", "message": "Nothing has been committed for this session yet."}), 404
    return jsonify({"success": True, "execution": execution.to_dict()})


@imports_bp.route("/executions/<int:execution_id>/rollback", methods=["POST"])
@login_required
def rollback_execution(execution_id):
    """
    Roll back a previously committed import execution: deletes everything
    it created and restores the old price on anything it updated.
    ---
    tags:
      - Imports
    parameters:
      - name: execution_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Rolled back
      404:
        description: Execution not found
      422:
        description: Already rolled back
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = ImportExecutionService(current_user.tenant_id, current_user.id)
    try:
        execution = service.rollback(execution_id)
    except HTTPException as exc:
        return _handle(exc)
    except ImportExecutionError as exc:
        return jsonify({"success": False, "error": "rollback_failed", "message": str(exc)}), 422

    db.session.commit()
    return jsonify({"success": True, "execution": execution.to_dict()})
