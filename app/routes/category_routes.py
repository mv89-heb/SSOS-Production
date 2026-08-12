from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from werkzeug.exceptions import BadRequest, NotFound, HTTPException

from app.extensions import db
from app.models.product import Product
from app.services.permission_service import PermissionService
from app.services.product_classification_service import ProductClassificationService

category_bp = Blueprint("categories", __name__, url_prefix="/api/catalog")
classifier = ProductClassificationService()


def _error(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


@category_bp.get("/categories")
@login_required
def list_categories():
    return jsonify({"success": True, "categories": classifier.categories()})


@category_bp.post("/products/<int:product_id>/classify")
@login_required
def classify_product(product_id):
    try:
        PermissionService.require_role_at_least("manager")
        product = Product.query.filter_by(id=product_id, tenant_id=current_user.tenant_id).first()
        if not product:
            raise NotFound("Product not found")
        result = classifier.classify(current_user.tenant_id, product.name)
        product.category = result["category"]
        product.category_source = result["source"]
        product.category_confidence = result["confidence"]
        product.category_reviewed = result["confidence"] >= 0.90
        db.session.commit()
        return jsonify({"success": True, "classification": result, "product": product.to_dict()})
    except HTTPException as exc:
        return _error(exc)


@category_bp.post("/products/<int:product_id>/category-feedback")
@login_required
def category_feedback(product_id):
    try:
        PermissionService.require_role_at_least("manager")
        payload = request.get_json(silent=True) or {}
        category = payload.get("category")
        if category not in classifier.categories():
            raise BadRequest("Invalid product category")
        product = Product.query.filter_by(id=product_id, tenant_id=current_user.tenant_id).first()
        if not product:
            raise NotFound("Product not found")
        result = classifier.classify(current_user.tenant_id, product.name)
        classifier.record_feedback(
            current_user.tenant_id,
            current_user.id,
            product.id,
            product.name,
            category,
            predicted_category=result.get("category"),
            confidence=result.get("confidence"),
        )
        product.category = category
        product.category_source = "USER"
        product.category_confidence = 1.0
        product.category_reviewed = True
        db.session.commit()
        return jsonify({"success": True, "product": product.to_dict()})
    except HTTPException as exc:
        return _error(exc)
