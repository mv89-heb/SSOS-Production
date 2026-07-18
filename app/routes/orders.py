import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from app.extensions import db
from app.services.order_service import OrderService
from app.services.ocr_service import OCRService, validate_upload, OCRProviderError
from app.services.permission_service import PermissionService

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")

def _handle(exc: HTTPException):
    """Helper to format JSON error responses."""
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description
    }), exc.code

@orders_bp.route("", methods=["GET"])
@login_required
def list_orders():
    """
    List all orders for the current tenant
    ---
    tags:
      - Orders
    parameters:
      - name: status
        in: query
        type: string
        description: Filter by order status (draft, submitted, approved, etc.)
      - name: limit
        in: query
        type: integer
        default: 50
      - name: offset
        in: query
        type: integer
        default: 0
    responses:
      200:
        description: A list of orders
        schema:
          type: object
          properties:
            success:
              type: boolean
            orders:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  order_number:
                    type: string
                  status:
                    type: string
                  final_total:
                    type: number
      400:
        description: Invalid status filter
    """
    status = request.args.get("status")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        orders = service.list_orders(status=status, limit=limit, offset=offset)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "orders": [o.to_dict() for o in orders]})

@orders_bp.route("", methods=["POST"])
@login_required
def create_order():
    """
    Create a new Order using Catalog Products (Snapshot Architecture)
    ---
    tags:
      - Orders
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - supplier_id
            - items
          properties:
            supplier_id:
              type: integer
              example: 1
            currency:
              type: string
              default: "ILS"
            notes:
              type: string
            items:
              type: array
              items:
                type: object
                required:
                  - product_id
                  - quantity
                properties:
                  product_id:
                    type: integer
                  quantity:
                    type: integer
    responses:
      201:
        description: Order created successfully with immutable snapshots of products
      400:
        description: Invalid input data
      404:
        description: Supplier or Product not found
    """
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.create_order(current_user, data)
    except HTTPException as exc:
        return _handle(exc)

    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()}), 201

@orders_bp.route("/<int:order_id>", methods=["GET"])
@login_required
def get_order(order_id):
    """
    Get detailed information about a specific order
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Detailed order object including items snapshot
      404:
        description: Order not found
    """
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.get_order(order_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>", methods=["PUT"])
@login_required
def update_order(order_id):
    """
    Update a draft order's notes/items. Status changes go through the
    dedicated /submit, /approve, /reject, /sent, /complete endpoints instead
    of this one, so each transition can carry its own precondition and
    permission checks.
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            notes:
              type: string
            items:
              type: array
    responses:
      200:
        description: Order updated
      400:
        description: status was included in the body — use a lifecycle endpoint instead
      409:
        description: Order is not editable (not in draft status)
    """
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    if "status" in data:
        return jsonify({
            "success": False,
            "error": "use_lifecycle_endpoint",
            "message": "Status changes must go through /submit, /approve, /reject, /sent, or /complete",
        }), 400

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.update_order(current_user, order_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>", methods=["DELETE"])
@login_required
def delete_order(order_id):
    """
    Delete a draft order
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Order deleted
      403:
        description: Insufficient permissions
      409:
        description: Cannot delete non-draft orders
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        service.delete_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True}), 200

@orders_bp.route("/<int:order_id>/submit", methods=["POST"])
@login_required
def submit_order(order_id):
    """
    Submit a draft order for approval — freezes its immutable Snapshot.
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Order submitted, snapshot frozen
      409:
        description: Order is not in draft status
    """
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.submit_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/approve", methods=["POST"])
@login_required
def approve_order(order_id):
    """
    Approve a submitted order (manager/admin only)
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Order approved
      403:
        description: Insufficient permissions
      409:
        description: Order is not in submitted status
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.approve_order(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/reject", methods=["POST"])
@login_required
def reject_order(order_id):
    """
    Reject a submitted order (manager/admin only)
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            reason:
              type: string
    responses:
      200:
        description: Order rejected
      403:
        description: Insufficient permissions
      409:
        description: Order is not in submitted status
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.reject_order(current_user, order_id, reason=data.get("reason", ""))
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/sent", methods=["POST"])
@login_required
def mark_order_sent(order_id):
    """
    Mark an approved order as sent to the supplier (manager/admin only)
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Order marked sent
      409:
        description: Order is not in approved status
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.mark_sent(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/complete", methods=["POST"])
@login_required
def mark_order_completed(order_id):
    """
    Mark a sent order as completed (manager/admin only)
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Order marked completed
      409:
        description: Order is not in sent status
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        order = service.mark_completed(current_user, order_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "order": order.to_dict()})

@orders_bp.route("/<int:order_id>/ocr", methods=["POST"])
@login_required
def ocr_upload(order_id):
    """
    Upload a document for OCR processing against an order
    ---
    tags:
      - Orders
    parameters:
      - name: order_id
        in: path
        required: true
        type: integer
      - name: file
        in: formData
        type: file
        required: true
        description: The invoice image or PDF
    responses:
      200:
        description: OCR processing completed
      400:
        description: Invalid file or upload error
    """
    try:
        PermissionService.require_role_at_least("employee")
    except HTTPException as exc:
        return _handle(exc)

    service = OrderService(tenant_id=current_user.tenant_id)
    try:
        service.get_order(order_id)
    except HTTPException as exc:
        return _handle(exc)

    if "file" not in request.files:
        return jsonify({"success": False, "error": "no_file"}), 400

    upload = request.files["file"]
    if not upload.filename:
        return jsonify({"success": False, "error": "no_file"}), 400

    filename = secure_filename(upload.filename)
    mime_type = upload.mimetype

    upload.stream.seek(0, os.SEEK_END)
    file_size = upload.stream.tell()
    upload.stream.seek(0)

    try:
        validate_upload(
            filename, mime_type, file_size,
            max_size=current_app.config["MAX_CONTENT_LENGTH"],
        )
    except OCRProviderError as exc:
        return jsonify({"success": False, "error": "invalid_upload", "message": str(exc)}), 400

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    upload.save(save_path)

    result = OCRService().process_document(save_path)
    return jsonify({"success": result["status"] == "success", "result": result}), 200
