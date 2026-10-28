import io

import barcode
import qrcode
from barcode.writer import SVGWriter
from flask import Blueprint, current_app, jsonify, request, Response
from flask_login import current_user, login_required
from qrcode.image.svg import SvgPathImage
from werkzeug.exceptions import BadRequest, NotFound, HTTPException

from app.extensions import db
from app.models.product import Product
from app.models.product_code import ProductCode
from app.services.permission_service import PermissionService

product_codes_bp = Blueprint("product_codes", __name__, url_prefix="/api/product-codes")


def _error(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _product_or_404(product_id):
    product = db.session.scalar(db.select(Product).where(
        Product.id == product_id,
        Product.tenant_id == current_user.tenant_id,
    ))
    if product is None:
        raise NotFound("Product not found")
    return product


@product_codes_bp.route("/products/<int:product_id>", methods=["GET"])
@login_required
def list_product_codes(product_id):
    try:
        PermissionService.require_permission("catalog.view")
        _product_or_404(product_id)
        rows = db.session.scalars(db.select(ProductCode).where(
            ProductCode.tenant_id == current_user.tenant_id,
            ProductCode.product_id == product_id,
        ).order_by(ProductCode.id)).all()
        return jsonify({"success": True, "codes": [row.to_dict() for row in rows]})
    except HTTPException as exc:
        return _error(exc)


@product_codes_bp.route("/products/<int:product_id>/generate", methods=["POST"])
@login_required
def generate_product_codes(product_id):
    try:
        PermissionService.require_permission("catalog.manage")
        product = _product_or_404(product_id)
        payload = request.get_json(silent=True) or {}
        code_types = payload.get("types", ["CODE128", "QR"])
        if not isinstance(code_types, list) or not code_types or any(item not in {"CODE128", "QR"} for item in code_types):
            raise BadRequest("types must be a non-empty list containing CODE128 and/or QR")

        # Existing generated codes are returned unchanged: retries never create duplicates.
        existing = {row.code_type: row for row in db.session.scalars(db.select(ProductCode).where(
            ProductCode.tenant_id == current_user.tenant_id,
            ProductCode.product_id == product.id,
        )).all()}
        for code_type in dict.fromkeys(code_types):
            if code_type in existing:
                continue
            if code_type == "CODE128":
                value = f"SSOS{current_user.tenant_id:04d}{product.id:08d}"
            else:
                base_url = (current_app.config.get("FRONTEND_BASE_URL") or "https://ssos-production.onrender.com").rstrip("/")
                value = f"{base_url}/dashboard/catalog?product_id={product.id}"
            row = ProductCode(
                tenant_id=current_user.tenant_id,
                product_id=product.id,
                code_type=code_type,
                code_value=value,
                created_by=current_user.id,
            )
            db.session.add(row)
            existing[code_type] = row
        db.session.commit()
        return jsonify({"success": True, "codes": [existing[key].to_dict() for key in sorted(existing)]}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Product code generation failed")
        return jsonify({"success": False, "error": "internal_server_error", "message": "יצירת הקוד נכשלה. אפשר לנסות שוב."}), 500


@product_codes_bp.route("/<int:code_id>/image", methods=["GET"])
@login_required
def render_product_code(code_id):
    try:
        PermissionService.require_permission("catalog.view")
        row = db.session.scalar(db.select(ProductCode).where(
            ProductCode.id == code_id,
            ProductCode.tenant_id == current_user.tenant_id,
        ))
        if row is None:
            raise NotFound("Product code not found")
        output = io.BytesIO()
        if row.code_type == "QR":
            qr = qrcode.QRCode(box_size=8, border=4)
            qr.add_data(row.code_value)
            qr.make(fit=True)
            image = qr.make_image(image_factory=SvgPathImage)
            image.save(output)
        elif row.code_type == "CODE128":
            code_class = barcode.get_barcode_class("code128")
            image = code_class(row.code_value, writer=SVGWriter())
            image.write(output, options={"module_height": 15, "font_size": 10, "text_distance": 3, "quiet_zone": 3})
        else:
            raise BadRequest("Unsupported code type")
        return Response(output.getvalue(), mimetype="image/svg+xml", headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="product-code.svg"',
        })
    except HTTPException as exc:
        return _error(exc)
