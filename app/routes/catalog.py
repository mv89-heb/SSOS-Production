from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.exceptions import HTTPException, BadRequest
from app.extensions import db
from app.models.product import Product
from app.services.catalog_service import CatalogService
from app.services.permission_service import PermissionService
from app.services.product_image_service import lookup_product_image
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
    from app.models.supplier_product import SupplierProduct
    from app.models.supplier import Supplier
    from app.services.price_intelligence_service import PriceIntelligenceService

    query = str(request.args.get("q") or "").strip()
    limit = max(1, min(request.args.get("limit", 100, type=int) or 100, 1000))
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
    masters = db.session.execute(stmt.order_by(MasterProduct.canonical_name.asc(), MasterProduct.id.asc()).limit(limit)).scalars().all()
    master_ids = [master.id for master in masters]
    grouped = {master_id: [] for master_id in master_ids}
    if master_ids:
        rows = db.session.execute(
            select(SupplierProduct, Supplier)
            .join(Supplier, (Supplier.id == SupplierProduct.supplier_id) & (Supplier.tenant_id == current_user.tenant_id))
            .where(
                SupplierProduct.tenant_id == current_user.tenant_id,
                SupplierProduct.master_product_id.in_(master_ids),
                SupplierProduct.match_status == "APPROVED",
                SupplierProduct.active.is_(True),
                Supplier.active.is_(True),
            )
            .order_by(SupplierProduct.master_product_id.asc(), SupplierProduct.id.asc())
        ).all()
        for listing, supplier in rows:
            grouped[listing.master_product_id].append((listing, supplier))

    items = []
    for master in masters:
        listings = grouped.get(master.id, [])
        normalized = []
        for listing, supplier in listings:
            if listing.price is None or float(listing.price) <= 0:
                continue
            offer = PriceIntelligenceService._price_payload(
                listing.supplier_id, supplier.name, listing.price, listing.unit,
                listing.units_per_carton, listing.currency,
            )
            if offer["comparison_unit"] is not None:
                normalized.append((listing, supplier, offer))
        # Prices can only be compared within the same currency and normalized
        # unit. When listings contain mixed packaging, show the best price in
        # the largest comparable group instead of blanking the entire product.
        comparison_groups = {}
        for row in normalized:
            group_key = (row[2]["currency"], row[2]["comparison_unit"])
            comparison_groups.setdefault(group_key, []).append(row)
        selected_group_key = min(
            comparison_groups,
            key=lambda key: (-len(comparison_groups[key]), key[0], key[1]),
        ) if comparison_groups else None
        selected_group = comparison_groups.get(selected_group_key, [])
        best_pair = min(selected_group, key=lambda row: row[2]["normalized_price"]) if selected_group else None
        data = master.to_dict()
        data.update({
            "supplier_count": len({listing.supplier_id for listing, _ in listings if listing.price is not None and float(listing.price) > 0}),
            "listing_count": len(listings),
            "current_price": best_pair[2]["normalized_price"] if best_pair else None,
            "currency": best_pair[2]["currency"] if best_pair else "ILS",
            "comparison_unit": best_pair[2]["comparison_unit"] if best_pair else None,
            "comparable_supplier_count": len(selected_group),
            "best_supplier_name": best_pair[1].name if best_pair else None,
            "has_price": best_pair is not None,
        })
        items.append(data)
    return jsonify({"success": True, "master_products": items, "total": len(items)})


@catalog_bp.route("/master-products/review-candidates", methods=["GET"])
@login_required
def review_master_product_candidates():
    from sqlalchemy import select
    from app.models.master_product import MasterProduct
    from app.models.supplier_product import SupplierProduct
    from app.models.supplier import Supplier
    from app.services.master_product_matching_service import MasterProductMatchingService

    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    tenant_id = current_user.tenant_id
    limit = max(1, min(request.args.get("limit", 100, type=int), 250))
    service = MasterProductMatchingService(tenant_id, current_user.id)
    masters = db.session.execute(select(MasterProduct).where(
        MasterProduct.tenant_id == tenant_id, MasterProduct.active.is_(True)
    ).order_by(MasterProduct.id.asc())).scalars().all()
    rows = db.session.execute(
        select(SupplierProduct, Supplier)
        .join(Supplier, (Supplier.id == SupplierProduct.supplier_id) & (Supplier.tenant_id == tenant_id))
        .where(
            SupplierProduct.tenant_id == tenant_id,
            SupplierProduct.match_status == "APPROVED",
            SupplierProduct.active.is_(True),
            Supplier.active.is_(True),
            SupplierProduct.master_product_id.is_not(None),
        )
        .order_by(SupplierProduct.updated_at.desc(), SupplierProduct.id.asc())
        .limit(limit)
    ).all()

    candidates = []
    for item, supplier in rows:
        matches = []
        incoming_barcode = "".join(ch for ch in str(item.barcode or "") if ch.isdigit())
        incoming_is_real = bool(incoming_barcode) and not service._is_synthetic_barcode(incoming_barcode)
        current_master = item.master_product
        for master in masters:
            if master.id == item.master_product_id:
                continue
            current_category = str((current_master.category if current_master else None) or "").strip().casefold()
            candidate_category = str(master.category or "").strip().casefold()
            if current_category and candidate_category and current_category != candidate_category:
                continue
            current_unit = service.normalize((current_master.base_unit if current_master else None) or "")
            candidate_unit = service.normalize(master.base_unit or "")
            if current_unit and candidate_unit and current_unit != candidate_unit:
                continue
            incoming_package = (current_master.package_size, service.normalize(current_master.package_unit or "")) if current_master else (None, "")
            candidate_package = (master.package_size, service.normalize(master.package_unit or ""))
            if incoming_package[0] is not None and candidate_package[0] is not None and incoming_package != candidate_package:
                continue
            master_barcode = "".join(ch for ch in str(master.barcode or "") if ch.isdigit())
            master_is_real = bool(master_barcode) and not service._is_synthetic_barcode(master_barcode)
            if incoming_is_real and master_is_real and incoming_barcode != master_barcode:
                continue
            score, method = service._score(item.supplier_name, master.canonical_name)
            if score >= 0.82 and method not in {"PACKAGE_SIZE_MISMATCH", "PRODUCT_VARIANT_MISMATCH"}:
                matches.append((score, master, method))
        matches.sort(key=lambda match: (-match[0], match[1].id))
        if not matches or (len(matches) > 1 and matches[0][0] - matches[1][0] < 0.04):
            continue
        score, master, method = matches[0]
        candidates.append({
            "supplier_product": item.to_dict(),
            "supplier_company_name": supplier.name,
            "current_master_product": current_master.to_dict() if current_master else None,
            "suggested_master_product": master.to_dict(),
            "confidence": score,
            "match_method": method,
        })
    candidates.sort(key=lambda candidate: (-candidate["confidence"], candidate["supplier_product"]["id"]))
    return jsonify({"success": True, "candidates": candidates})


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


@catalog_bp.route("/master-products/<int:master_product_id>/comparison", methods=["GET"])
@login_required
def compare_master_product(master_product_id):
    from app.services.master_product_matching_service import MasterProductMatchingService
    try:
        result = MasterProductMatchingService(current_user.tenant_id, current_user.id).compare_master_product(master_product_id)
        return jsonify({"success": True, **result})
    except HTTPException as exc:
        return _handle(exc)


@catalog_bp.route("/products/images/enrich", methods=["POST"])
@login_required
def enrich_missing_product_images():
    """Fill missing catalog images only when Open Food Facts confirms the exact barcode."""
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    payload = request.get_json(silent=True) or {}
    try:
        limit = int(payload.get("limit", 40))
    except (TypeError, ValueError):
        raise BadRequest("limit must be an integer")
    if limit < 1 or limit > 100:
        raise BadRequest("limit must be between 1 and 100")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    candidates = (
        Product.query.filter_by(tenant_id=current_user.tenant_id, active=True)
        .filter(db.or_(Product.image_url.is_(None), db.func.trim(Product.image_url) == ""))
        .filter(db.or_(Product.image_checked_at.is_(None), Product.image_checked_at < cutoff))
        .order_by(Product.id.asc()).all()
    )
    eligible = []
    missing_barcode = 0
    for product in candidates:
        barcode = str(product.barcode or "").strip()
        if not barcode or not barcode.isdigit() or barcode.startswith("990000010000"):
            missing_barcode += 1
            continue
        eligible.append(product)

    batch = eligible[:limit]
    matched = []
    no_match = 0
    for product in batch:
        result = lookup_product_image(product.barcode)
        product.image_checked_at = now
        if result.get("image_url"):
            # Never overwrite a manually supplied image; the query above only
            # includes blank image URLs. The source is kept for future refreshes.
            product.image_url = result["image_url"]
            product.image_source = result.get("source") or "Open Food Facts"
            product.image_source_url = result.get("source_url")
            matched.append({"product_id": product.id, "name": product.name, "image_url": product.image_url})
        else:
            no_match += 1
    db.session.commit()
    return jsonify({
        "success": True,
        "attempted": len(batch),
        "matched": len(matched),
        "no_match": no_match,
        "remaining_eligible": max(0, len(eligible) - len(batch)),
        "missing_or_synthetic_barcode": missing_barcode,
        "matches": matched,
        "source": "Open Food Facts",
        "policy": "Only exact barcode matches are accepted; existing image URLs are never overwritten.",
    })
