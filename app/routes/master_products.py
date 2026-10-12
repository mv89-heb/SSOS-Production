from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from werkzeug.exceptions import HTTPException, BadRequest

from app.extensions import db
from app.models.master_product import MasterProduct
from app.models.supplier_product import SupplierProduct
from app.services.master_product_matching_service import MasterProductMatchingService
from app.services.price_intelligence_service import PriceIntelligenceService
from app.services.permission_service import PermissionService

master_products_bp = Blueprint("master_products", __name__, url_prefix="/api/master-products")


def _error(exc):
    return jsonify({"success": False, "message": exc.description}), exc.code


@master_products_bp.get("")
@login_required
def list_master_products():
    query = str(request.args.get("q") or "").strip()
    limit = max(1, min(request.args.get("limit", default=500, type=int), 1000))
    stmt = select(MasterProduct).where(
        MasterProduct.tenant_id == current_user.tenant_id,
        MasterProduct.active.is_(True),
    )
    if query:
        stmt = stmt.where(MasterProduct.canonical_name.ilike(f"%{query}%"))
    masters = db.session.execute(stmt.order_by(MasterProduct.canonical_name.asc(), MasterProduct.id.asc()).limit(limit)).scalars().all()
    items = []
    for master in masters:
        listings = db.session.execute(select(SupplierProduct).where(
            SupplierProduct.tenant_id == current_user.tenant_id,
            SupplierProduct.master_product_id == master.id,
            SupplierProduct.match_status == "APPROVED",
            SupplierProduct.active.is_(True),
        )).scalars().all()
        priced = [item for item in listings if item.price is not None and float(item.price) > 0]
        normalized = []
        for item in priced:
            row = PriceIntelligenceService._price_payload(
                item.supplier_id, item.supplier.name if item.supplier else None,
                item.price, item.unit, item.units_per_carton, item.currency,
            )
            if row["comparison_unit"] is not None:
                normalized.append((item, row))
        comparison_keys = {(row["currency"], row["comparison_unit"]) for _, row in normalized}
        # A single best price is meaningful only when all priced listings can
        # be normalized to the same currency and comparison unit.
        best_pair = min(normalized, key=lambda pair: pair[1]["normalized_price"]) if normalized and len(comparison_keys) == 1 else None
        best = best_pair[0] if best_pair else None
        best_price = best_pair[1]["normalized_price"] if best_pair else None
        best_currency = best_pair[1]["currency"] if best_pair else None
        data = master.to_dict()
        data.update({
            "masterProductId": master.id,
            "name": master.canonical_name,
            "current_price": best_price,
            "currency": best_currency or "ILS",
            "supplier_count": len({item.supplier_id for item in priced}),
            "listing_count": len(listings),
            "best_supplier_name": best.supplier.name if best and best.supplier and best_price is not None else None,
            "has_price": best_price is not None,
        })
        items.append(data)
    return jsonify({"success": True, "products": items, "total": len(items)})


@master_products_bp.get("/pending")
@login_required
def list_pending_supplier_products():
    service = MasterProductMatchingService(current_user.tenant_id, current_user.id)
    return jsonify({"success": True, "items": [item.to_dict() for item in service.pending()]})


@master_products_bp.get("/<int:master_product_id>/comparison")
@login_required
def compare_master_product(master_product_id):
    try:
        result = MasterProductMatchingService(current_user.tenant_id, current_user.id).compare_master_product(master_product_id)
        return jsonify({"success": True, **result})
    except HTTPException as exc:
        return _error(exc)


@master_products_bp.post("/suggest")
@login_required
def suggest_master_product():
    data = request.get_json(silent=True) or {}
    try:
        name = str(data.get("name") or data.get("supplier_name") or "").strip()
        if not name:
            raise BadRequest("יש להזין שם מוצר")
        suggestions = MasterProductMatchingService(current_user.tenant_id, current_user.id).suggest(name, data.get("barcode"))
        return jsonify({"success": True, "suggestions": suggestions})
    except HTTPException as exc:
        return _error(exc)


@master_products_bp.post("/supplier-products")
@login_required
def intake_supplier_product():
    try:
        PermissionService.require_role_at_least("manager")
        data = request.get_json(silent=True) or {}
        item, suggestions = MasterProductMatchingService(current_user.tenant_id, current_user.id).intake(data)
        db.session.commit()
        return jsonify({"success": True, "item": item.to_dict(), "suggestions": suggestions}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)


@master_products_bp.post("/supplier-products/<int:supplier_product_id>/approve")
@login_required
def approve_supplier_product(supplier_product_id):
    try:
        PermissionService.require_role_at_least("manager")
        data = request.get_json(silent=True) or {}
        try:
            master_id = int(data.get("master_product_id"))
        except (TypeError, ValueError):
            raise BadRequest("נדרש master_product_id תקין")
        item = MasterProductMatchingService(current_user.tenant_id, current_user.id).approve(supplier_product_id, master_id)
        db.session.commit()
        return jsonify({"success": True, "item": item.to_dict()})
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)


@master_products_bp.post("/supplier-products/<int:supplier_product_id>/create-master")
@login_required
def create_master_from_supplier_product(supplier_product_id):
    try:
        PermissionService.require_role_at_least("manager")
        data = request.get_json(silent=True) or {}
        item, master = MasterProductMatchingService(current_user.tenant_id, current_user.id).create_master_and_approve(supplier_product_id, data)
        db.session.commit()
        return jsonify({"success": True, "item": item.to_dict(), "master_product": master.to_dict()}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
