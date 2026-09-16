from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from werkzeug.exceptions import BadRequest, HTTPException

from app.extensions import db
from app.models.inventory_movement import InventoryMovement, VALID_MOVEMENT_TYPES
from app.models.product import Product
from app.services.inventory_planning_service import InventoryPlanningService
from app.services.permission_service import PermissionService

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


def _handle(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


def _internal_barcode(product: Product) -> str:
    return f"SSOS-{product.tenant_id:04d}-{product.id:08d}"


def _generate_missing_barcodes(products):
    generated = []
    for product in products:
        if product.barcode and product.barcode.strip():
            continue
        product.barcode = _internal_barcode(product)
        generated.append(product)
    if generated:
        db.session.flush()
    return generated


@inventory_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    products = db.session.scalars(
        select(Product)
        .where(Product.tenant_id == current_user.tenant_id, Product.active.is_(True))
        .order_by(Product.name.asc())
    ).all()
    product_ids = [p.id for p in products]
    movements = []
    if product_ids:
        movements = db.session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.tenant_id == current_user.tenant_id,
                InventoryMovement.product_id.in_(product_ids),
            )
            .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
            .limit(500)
        ).all()

    low_stock = [p for p in products if p.min_stock is not None and (p.current_stock or 0) <= p.min_stock]
    out_of_stock = [p for p in products if (p.current_stock or 0) <= 0]
    no_stock_rule = [p for p in products if p.min_stock is None and p.recommended_stock is None]
    return jsonify({
        "success": True,
        "stats": {
            "active_products": len(products),
            "low_stock": len(low_stock),
            "out_of_stock": len(out_of_stock),
            "without_stock_rule": len(no_stock_rule),
            "movement_count": len(movements),
        },
        "products": [p.to_dict() for p in products],
        "recent_movements": [m.to_dict() for m in movements[:50]],
    })


@inventory_bp.route("/barcodes/generate", methods=["POST"])
@login_required
def generate_barcodes():
    """Generate stable internal barcodes for products that do not have one."""
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("product_ids")
    include_inactive = bool(payload.get("include_inactive", False))

    statement = select(Product).where(Product.tenant_id == current_user.tenant_id)
    if not include_inactive:
        statement = statement.where(Product.active.is_(True))

    if raw_ids is not None:
        if not isinstance(raw_ids, list) or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in raw_ids
        ):
            return _handle(BadRequest("product_ids must be a list of positive integers"))
        if len(raw_ids) > 5000:
            return _handle(BadRequest("Too many products requested"))
        statement = statement.where(Product.id.in_(raw_ids))

    products = db.session.scalars(statement.order_by(Product.id.asc())).all()
    generated = _generate_missing_barcodes(products)
    skipped_count = len(products) - len(generated)
    db.session.commit()
    return jsonify({
        "success": True,
        "generated_count": len(generated),
        "skipped_count": skipped_count,
        "products": [product.to_dict() for product in generated],
        "skipped_product_ids": [product.id for product in products if product not in generated],
        "format": "Code 128",
    })


@inventory_bp.route("/barcodes/labels", methods=["POST"])
@login_required
def barcode_labels():
    """Generate an A4 PDF containing printable Code 128 labels."""
    try:
        PermissionService.require_role_at_least("manager")
    except HTTPException as exc:
        return _handle(exc)

    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("product_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return _handle(BadRequest("product_ids must be a non-empty list"))
    if len(raw_ids) > 5000 or any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in raw_ids
    ):
        return _handle(BadRequest("product_ids must contain up to 5000 positive integers"))

    products = db.session.scalars(
        select(Product)
        .where(Product.tenant_id == current_user.tenant_id, Product.id.in_(raw_ids), Product.active.is_(True))
        .order_by(Product.name.asc(), Product.id.asc())
    ).all()
    if not products:
        return _handle(BadRequest("No active products found"))

    _generate_missing_barcodes(products)
    db.session.commit()

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        from reportlab.graphics.barcode import code128
    except ImportError:
        db.session.rollback()
        return _handle(HTTPException(description="PDF label support is not installed"))

    font_name = "Helvetica"
    for font_path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        try:
            pdfmetrics.registerFont(TTFont("InventoryLabelFont", font_path))
            font_name = "InventoryLabelFont"
            break
        except Exception:
            continue

    buffer = BytesIO()
    page_width, page_height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    columns, rows = 2, 5
    margin_x, margin_y = 8 * mm, 8 * mm
    gap_x, gap_y = 4 * mm, 4 * mm
    label_width = (page_width - 2 * margin_x - gap_x) / columns
    label_height = (page_height - 2 * margin_y - gap_y * (rows - 1)) / rows

    for index, product in enumerate(products):
        position = index % (columns * rows)
        if position == 0 and index:
            pdf.showPage()
        col = position % columns
        row = position // columns
        x = margin_x + col * (label_width + gap_x)
        y = page_height - margin_y - (row + 1) * label_height - row * gap_y

        pdf.setLineWidth(0.5)
        pdf.roundRect(x, y, label_width, label_height, 3 * mm, stroke=1, fill=0)
        pdf.setFont(font_name, 9)
        product_name = product.name or "מוצר"
        if len(product_name) > 42:
            product_name = product_name[:39] + "..."
        pdf.drawRightString(x + label_width - 5 * mm, y + label_height - 8 * mm, product_name)

        barcode_value = product.barcode
        barcode = code128.Code128(barcode_value, barHeight=18 * mm, humanReadable=True)
        scale = min((label_width - 10 * mm) / barcode.width, 1.0)
        barcode.drawOn(pdf, x + (label_width - barcode.width * scale) / 2, y + 12 * mm)

        pdf.setFont(font_name, 7)
        pdf.drawCentredString(x + label_width / 2, y + 5 * mm, barcode_value)

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=False, download_name="inventory-barcode-labels.pdf")


@inventory_bp.route("/products/lookup", methods=["GET"])
@login_required
def lookup_product():
    """Find one active tenant product by exact barcode or SKU."""
    value = str(request.args.get("value") or "").strip()
    if not value:
        return _handle(BadRequest("value is required"))
    if len(value) > 100:
        return _handle(BadRequest("value is too long"))

    product = db.session.scalar(
        select(Product)
        .where(
            Product.tenant_id == current_user.tenant_id,
            Product.active.is_(True),
            or_(Product.barcode == value, Product.sku == value),
        )
        .limit(1)
    )
    if product is None:
        from werkzeug.exceptions import NotFound
        return _handle(NotFound("Product not found"))
    return jsonify({"success": True, "product": product.to_dict()})


@inventory_bp.route("/movements", methods=["GET"])
@login_required
def list_movements():
    product_id = request.args.get("product_id", type=int)
    movement_type = (request.args.get("movement_type") or "").strip().lower()
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    if movement_type and movement_type not in VALID_MOVEMENT_TYPES:
        return _handle(BadRequest("movement_type is invalid"))

    statement = select(InventoryMovement).where(InventoryMovement.tenant_id == current_user.tenant_id)
    if product_id is not None:
        statement = statement.where(InventoryMovement.product_id == product_id)
    if movement_type:
        statement = statement.where(InventoryMovement.movement_type == movement_type)
    rows = db.session.scalars(
        statement.order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc()).limit(limit)
    ).all()
    return jsonify({"success": True, "movements": [row.to_dict() for row in rows]})


@inventory_bp.route("/products/<int:product_id>/movements", methods=["GET"])
@login_required
def product_movements(product_id):
    limit = max(1, min(request.args.get("limit", default=100, type=int), 500))
    product = db.session.scalar(
        select(Product).where(Product.id == product_id, Product.tenant_id == current_user.tenant_id)
    )
    if product is None:
        from werkzeug.exceptions import NotFound
        return _handle(NotFound("Product not found"))
    rows = db.session.scalars(
        select(InventoryMovement)
        .where(
            InventoryMovement.tenant_id == current_user.tenant_id,
            InventoryMovement.product_id == product_id,
        )
        .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
        .limit(limit)
    ).all()
    return jsonify({"success": True, "product": product.to_dict(), "movements": [row.to_dict() for row in rows]})


@inventory_bp.route("/movements", methods=["POST"])
@login_required
def create_movement():
    payload = request.get_json(silent=True) or {}
    product_id = payload.get("product_id")
    movement_type = str(payload.get("movement_type") or "").strip().lower()
    quantity = payload.get("quantity")
    if not product_id or not movement_type or quantity is None:
        return _handle(BadRequest("product_id, movement_type and quantity are required"))
    if movement_type not in VALID_MOVEMENT_TYPES:
        return _handle(BadRequest("movement_type is invalid"))

    try:
        occurred_at = None
        raw_occurred_at = payload.get("occurred_at")
        if raw_occurred_at:
            occurred_at = datetime.fromisoformat(str(raw_occurred_at).replace("Z", "+00:00"))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        movement = InventoryPlanningService(current_user.tenant_id).record_movement(
            product_id=product_id,
            movement_type=movement_type,
            quantity=quantity,
            user_id=current_user.id,
            reference_type=payload.get("reference_type"),
            reference_id=payload.get("reference_id"),
            note=str(payload.get("note") or "").strip() or None,
            occurred_at=occurred_at,
        )
        db.session.commit()
        return jsonify({"success": True, "movement": movement.to_dict()}), 201
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return _handle(BadRequest(str(exc)))
    except HTTPException as exc:
        db.session.rollback()
        return _handle(exc)
    except Exception:
        db.session.rollback()
        raise
