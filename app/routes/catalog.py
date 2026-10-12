from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException
from app.extensions import db
from app.services.catalog_service import CatalogService
from app.services.permission_service import PermissionService
from app.utils.validators import validate_product_payload

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
            image_url:
              type: string
            barcode:
              type: string
            category:
              type: string
            unit:
              type: string
              example: "יחידה"
            units_per_carton:
              type: integer
            supplier_sku:
              type: string
            current_stock:
              type: integer
            min_stock:
              type: integer
            recommended_stock:
              type: integer
    responses:
      201:
        description: Product created
      400:
        description: Invalid product data
      404:
        description: Supplier not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    validation_error = validate_product_payload(data)
    if validation_error:
        return jsonify({"success": False, "error": "invalid_product_data", "message": validation_error}), 400

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
            image_url:
              type: string
            barcode:
              type: string
            category:
              type: string
            unit:
              type: string
            units_per_carton:
              type: integer
            supplier_sku:
              type: string
            current_stock:
              type: integer
            min_stock:
              type: integer
            recommended_stock:
              type: integer
    responses:
      200:
        description: Product updated
      400:
        description: Invalid product data
      404:
        description: Product not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    validation_error = validate_product_payload(data)
    if validation_error:
        return jsonify({"success": False, "error": "invalid_product_data", "message": validation_error}), 400

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


# ------------------------------------------------------------------------
# Phase 2: Supplier Catalog Engine — alternate-supplier price offers
# ------------------------------------------------------------------------

@catalog_bp.route("/products/<int:product_id>/offers", methods=["GET"])
@login_required
def list_offers(product_id):
    """
    List alternate-supplier price offers for a product (cheapest first).
    Comparison data only — does not affect order creation.
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
        description: List of offers
      404:
        description: Product not found
    """
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        offers = service.list_offers(product_id)
    except HTTPException as exc:
        return _handle(exc)
    return jsonify({"success": True, "offers": [o.to_dict() for o in offers]})


@catalog_bp.route("/products/<int:product_id>/offers", methods=["POST"])
@login_required
def create_offer(product_id):
    """
    Record another supplier's price for an existing product.
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
          required:
            - supplier_id
            - price
          properties:
            supplier_id:
              type: integer
            price:
              type: number
            currency:
              type: string
            supplier_sku:
              type: string
            unit:
              type: string
            units_per_carton:
              type: integer
    responses:
      201:
        description: Offer created
      400:
        description: Invalid offer data
      404:
        description: Product or supplier not found
      409:
        description: This supplier already has a price on file for this product
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        offer = service.create_offer(product_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "offer": offer.to_dict()}), 201


@catalog_bp.route("/products/<int:product_id>/offers/<int:offer_id>", methods=["PUT"])
@login_required
def update_offer(product_id, offer_id):
    """
    Update an alternate-supplier offer's price/details.
    ---
    tags:
      - Catalog
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
      - name: offer_id
        in: path
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            price:
              type: number
            currency:
              type: string
            supplier_sku:
              type: string
            unit:
              type: string
            units_per_carton:
              type: integer
            active:
              type: boolean
    responses:
      200:
        description: Offer updated
      400:
        description: Invalid offer data
      404:
        description: Offer not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    data = request.get_json(silent=True) or {}
    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        offer = service.update_offer(product_id, offer_id, data)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True, "offer": offer.to_dict()})


@catalog_bp.route("/products/<int:product_id>/offers/<int:offer_id>", methods=["DELETE"])
@login_required
def delete_offer(product_id, offer_id):
    """
    Remove an alternate-supplier offer.
    ---
    tags:
      - Catalog
    parameters:
      - name: product_id
        in: path
        required: true
        type: integer
      - name: offer_id
        in: path
        required: true
        type: integer
    responses:
      200:
        description: Offer deleted
      404:
        description: Offer not found
    """
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    service = CatalogService(current_user.tenant_id, current_user.id)
    try:
        service.delete_offer(product_id, offer_id)
    except HTTPException as exc:
        return _handle(exc)
    db.session.commit()
    return jsonify({"success": True}), 200


# ------------------------------------------------------------------------
# Canonical master products and supplier-product matching workflow
# ------------------------------------------------------------------------

@catalog_bp.route("/master-products/match-suggestions", methods=["POST"])
@login_required
def master_product_match_suggestions():
    from app.services.master_product_matching_service import MasterProductMatchingService
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or data.get("supplier_name") or data.get("description") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "invalid_product_name", "message": "יש להזין שם מוצר לחיפוש"}), 400
    service = MasterProductMatchingService(current_user.tenant_id, current_user.id)
    return jsonify({"success": True, "suggestions": service.suggest(name, data.get("barcode"), data.get("limit", 5))})


@catalog_bp.route("/master-products", methods=["GET"])
@login_required
def list_master_products():
    from sqlalchemy import select, or_
    from app.models.master_product import MasterProduct
    query = str(request.args.get("q") or "").strip()
    limit = max(1, min(request.args.get("limit", 100, type=int) or 100, 250))
    stmt = select(MasterProduct).where(
        MasterProduct.tenant_id == current_user.tenant_id,
        MasterProduct.active.is_(True),
    )
    if query:
        pattern = "%" + query.replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(
            MasterProduct.canonical_name.ilike(pattern),
            MasterProduct.normalized_name.ilike(pattern),
            MasterProduct.barcode == query,
        ))
    masters = db.session.execute(stmt.order_by(MasterProduct.canonical_name.asc()).limit(limit)).scalars().all()
    return jsonify({"success": True, "master_products": [m.to_dict() for m in masters]})


@catalog_bp.route("/supplier-products/intake", methods=["POST"])
@login_required
def intake_supplier_product():
    from app.services.master_product_matching_service import MasterProductMatchingService
    try:
        PermissionService.require_role_at_least("manager")
        item, suggestions = MasterProductMatchingService(
            current_user.tenant_id, current_user.id
        ).intake(request.get_json(silent=True) or {})
        db.session.commit()
        return jsonify({
            "success": True, "supplier_product": item.to_dict(),
            "suggestions": suggestions,
        }), 201
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": "invalid_supplier_product", "message": str(exc)}), 400


@catalog_bp.route("/supplier-products/pending", methods=["GET"])
@login_required
def list_pending_supplier_products():
    from app.services.master_product_matching_service import MasterProductMatchingService
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)
    service = MasterProductMatchingService(current_user.tenant_id, current_user.id)
    items = service.pending(request.args.get("limit", 100, type=int) or 100)
    return jsonify({"success": True, "supplier_products": [item.to_dict() for item in items]})


@catalog_bp.route("/supplier-products/<int:supplier_product_id>/approve", methods=["POST"])
@login_required
def approve_supplier_product_match(supplier_product_id):
    from app.services.master_product_matching_service import MasterProductMatchingService
    data = request.get_json(silent=True) or {}
    try:
        PermissionService.require_role_at_least("manager")
        service = MasterProductMatchingService(current_user.tenant_id, current_user.id)
        if data.get("create_master_product"):
            item, master = service.create_master_and_approve(supplier_product_id, data["create_master_product"])
            db.session.commit()
            return jsonify({"success": True, "supplier_product": item.to_dict(), "master_product": master.to_dict()})
        try:
            master_id = int(data.get("master_product_id"))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "master_product_required", "message": "יש לבחור מוצר אב קיים או ליצור מוצר אב חדש"}), 400
        item = service.approve(supplier_product_id, master_id)
        db.session.commit()
        return jsonify({"success": True, "supplier_product": item.to_dict()})
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": "invalid_match", "message": str(exc)}), 400


@catalog_bp.route("/supplier-products/<int:supplier_product_id>/reject", methods=["POST"])
@login_required
def reject_supplier_product_match(supplier_product_id):
    from sqlalchemy import select
    from app.models.supplier_product import SupplierProduct
    from app.services.audit_service import AuditService
    try:
        PermissionService.require_role_at_least("manager")
        item = db.session.execute(select(SupplierProduct).where(
            SupplierProduct.id == supplier_product_id,
            SupplierProduct.tenant_id == current_user.tenant_id,
        )).scalar_one_or_none()
        if item is None:
            from werkzeug.exceptions import NotFound
            raise NotFound("פריט הספק לא נמצא")
        item.match_status = "REJECTED"
        item.master_product_id = None
        db.session.flush()
        AuditService.log_event(current_user.tenant_id, current_user.id, "supplier_product.match_rejected", "נדחתה הצעת שיוך מוצר ספק", {
            "supplier_product_id": item.id,
        })
        db.session.commit()
        return jsonify({"success": True, "supplier_product": item.to_dict()})
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
