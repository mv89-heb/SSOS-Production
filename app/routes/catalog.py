from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
from app.extensions import db
from app.services.catalog_service import CatalogService
from app.services.permission_service import PermissionService

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/catalog")

def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description
    }), exc.code

@catalog_bp.route("/suppliers", methods=["GET"])
@login_required
def list_suppliers():
    """
    List all suppliers for the current tenant
    ---
    tags:
      - Catalog
    responses:
      200:
        description: A list of suppliers
    """
    service = CatalogService(current_user.tenant_id, current_user.id)
    suppliers = service.list_suppliers(active_only=request.args.get("active") == "true")
    return jsonify({"success": True, "suppliers": [s.to_dict() for s in suppliers]})

@catalog_bp.route("/suppliers", methods=["POST"])
@login_required
def create_supplier():
    """
    Create a new supplier
    ---
    tags:
      - Catalog
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
            contact_name:
              type: string
            email:
              type: string
            phone:
              type: string
    responses:
      201:
        description: Supplier created
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    supplier = service.create_supplier(data)
    db.session.commit()
    return jsonify({"success": True, "supplier": supplier.to_dict()}), 201

@catalog_bp.route("/suppliers/<int:supplier_id>", methods=["GET"])
@login_required
def get_supplier(supplier_id):
    """
    Get a single supplier
    ---
    tags:
      - Catalog
    parameters:
      - name: supplier_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Supplier details
      404:
        description: Supplier not found
    """
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        supplier = service.get_supplier(supplier_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "supplier": supplier.to_dict()})

@catalog_bp.route("/suppliers/<int:supplier_id>", methods=["PUT"])
@login_required
def update_supplier(supplier_id):
    """
    Update a supplier
    ---
    tags:
      - Catalog
    parameters:
      - name: supplier_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
            contact_name:
              type: string
            email:
              type: string
            phone:
              type: string
            active:
              type: boolean
    responses:
      200:
        description: Supplier updated
      404:
        description: Supplier not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        supplier = service.update_supplier(supplier_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "supplier": supplier.to_dict()})

@catalog_bp.route("/products", methods=["GET"])
@login_required
def list_products():
    """
    List all products
    ---
    tags:
      - Catalog
    parameters:
      - name: supplier_id
        in: query
        type: integer
      - name: active
        in: query
        type: string
        description: "'true' to return only active products"
    responses:
      200:
        description: List of products
    """
    supplier_id = request.args.get("supplier_id", type=int)
    active_only = request.args.get("active") == "true"
    service = CatalogService(current_user.tenant_id, current_user.id)
    products = service.list_products(supplier_id=supplier_id, active_only=active_only)
    return jsonify({"success": True, "products": [p.to_dict() for p in products]})

@catalog_bp.route("/products", methods=["POST"])
@login_required
def create_product():
    """
    Create a new product
    ---
    tags:
      - Catalog
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - supplier_id
            - name
          properties:
            supplier_id:
              type: integer
            name:
              type: string
            sku:
              type: string
            description:
              type: string
            current_price:
              type: number
            currency:
              type: string
    responses:
      201:
        description: Product created
      404:
        description: Supplier not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        product = service.create_product(data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict()}), 201

@catalog_bp.route("/products/<int:product_id>", methods=["GET"])
@login_required
def get_product(product_id):
    """
    Get a single product
    ---
    tags:
      - Catalog
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Product details
      404:
        description: Product not found
    """
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        product = service.get_product(product_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "product": product.to_dict()})

@catalog_bp.route("/products/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    """
    Update a product's live catalog data. Existing orders keep the
    name/sku/price they captured at creation time — this never rewrites
    an existing order (Snapshot Integrity).
    ---
    tags:
      - Catalog
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
            sku:
              type: string
            description:
              type: string
            current_price:
              type: number
            currency:
              type: string
            active:
              type: boolean
    responses:
      200:
        description: Product updated
      404:
        description: Product not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        product = service.update_product(product_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict()})

@catalog_bp.route("/products/<int:product_id>", methods=["DELETE"])
@login_required
def delete_product(product_id):
    """
    Delete a product from the live catalog. Orders already created
    against it are unaffected (Snapshot Integrity).
    ---
    tags:
      - Catalog
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Product deleted
      403:
        description: Insufficient permissions
      404:
        description: Product not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        service.delete_product(product_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True}), 200
