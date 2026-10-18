from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
import os

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.order import Order
from app.models.receipt import Receipt
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoicePayment
from app.services.permission_service import PermissionService

supplier_invoices_bp = Blueprint("supplier_invoices", __name__, url_prefix="/api")


def _error(exc: HTTPException):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _date(value, field, required=False):
    if value in (None, ""):
        if required:
            raise BadRequest(f"{field} is required")
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{field} must be an ISO date (YYYY-MM-DD)")


def _amount(value, field="amount"):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise BadRequest(f"{field} must be a valid number")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
        raise BadRequest(f"{field} must be greater than zero and within the supported limit")
    return amount.quantize(Decimal("0.01"))


@supplier_invoices_bp.route("/orders/<int:order_id>/invoices", methods=["GET"])
@login_required
def list_order_invoices(order_id):
    order = db.session.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == current_user.tenant_id))
    if order is None:
        return _error(NotFound("Order not found"))
    invoices = db.session.scalars(
        select(SupplierInvoice).where(
            SupplierInvoice.tenant_id == current_user.tenant_id,
            SupplierInvoice.order_id == order_id,
        ).order_by(SupplierInvoice.invoice_date.desc(), SupplierInvoice.id.desc())
    ).all()
    return jsonify({"success": True, "invoices": [invoice.to_dict() for invoice in invoices]})


@supplier_invoices_bp.route("/orders/<int:order_id>/invoices", methods=["POST"])
@login_required
def create_order_invoice(order_id):
    try:
        PermissionService.require_role_at_least("employee")
        data = request.get_json(silent=True) or {}
        order = db.session.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == current_user.tenant_id))
        if order is None:
            raise NotFound("Order not found")
        invoice_number = str(data.get("invoice_number") or "").strip()
        if not invoice_number or len(invoice_number) > 120:
            raise BadRequest("invoice_number is required (max 120 characters)")
        currency = str(data.get("currency") or order.currency or "ILS").upper().strip()
        if len(currency) != 3 or not currency.isalpha():
            raise BadRequest("currency must be a three-letter code")
        receipt_id = data.get("receipt_id")
        if receipt_id not in (None, ""):
            if not isinstance(receipt_id, int) or isinstance(receipt_id, bool):
                raise BadRequest("receipt_id must be an integer")
            receipt = db.session.scalar(select(Receipt).where(
                Receipt.id == receipt_id, Receipt.order_id == order_id,
                Receipt.tenant_id == current_user.tenant_id,
            ))
            if receipt is None:
                raise NotFound("Receipt not found for this order")
        invoice = SupplierInvoice(
            tenant_id=current_user.tenant_id, order_id=order.id, supplier_id=order.supplier_id,
            receipt_id=int(receipt_id) if receipt_id not in (None, "") else None,
            invoice_number=invoice_number, invoice_date=_date(data.get("invoice_date"), "invoice_date"),
            due_date=_date(data.get("due_date"), "due_date"), amount=_amount(data.get("amount")),
            currency=currency, notes=str(data.get("notes") or "").strip()[:5000] or None,
            created_by=current_user.id,
        )
        db.session.add(invoice)
        db.session.flush()
        result = invoice.to_dict()
        db.session.commit()
        return jsonify({"success": True, "invoice": result}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise


@supplier_invoices_bp.route("/supplier-invoices/<int:invoice_id>/payments", methods=["POST"])
@login_required
def record_invoice_payment(invoice_id):
    try:
        PermissionService.require_role_at_least("employee")
        invoice = db.session.scalar(select(SupplierInvoice).where(
            SupplierInvoice.id == invoice_id,
            SupplierInvoice.tenant_id == current_user.tenant_id,
        ).with_for_update())
        if invoice is None:
            raise NotFound("Supplier invoice not found")
        data = request.get_json(silent=True) or {}
        amount = _amount(data.get("amount"))
        paid = sum((Decimal(str(payment.amount)) for payment in invoice.payments), Decimal("0"))
        if paid + amount > Decimal(str(invoice.amount)):
            raise Conflict("Payment exceeds the outstanding invoice balance")
        payment = SupplierInvoicePayment(
            tenant_id=current_user.tenant_id, invoice_id=invoice.id, amount=amount,
            payment_date=_date(data.get("payment_date"), "payment_date", required=True),
            reference=str(data.get("reference") or "").strip()[:255] or None,
            notes=str(data.get("notes") or "").strip()[:5000] or None,
            created_by=current_user.id,
        )
        db.session.add(payment)
        db.session.flush()
        result = invoice.to_dict()
        db.session.commit()
        return jsonify({"success": True, "invoice": result}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise


_ALLOWED_ATTACHMENTS = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\\xff\\xd8\\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\\xff\\xd8\\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\\x89PNG\\r\\n\\x1a\\n")),
}


def _invoice_for_tenant(invoice_id):
    invoice = db.session.scalar(select(SupplierInvoice).where(
        SupplierInvoice.id == invoice_id,
        SupplierInvoice.tenant_id == current_user.tenant_id,
    ))
    if invoice is None:
        raise NotFound("Supplier invoice not found")
    return invoice


@supplier_invoices_bp.route("/supplier-invoices/<int:invoice_id>/attachment", methods=["POST"])
@login_required
def upload_supplier_invoice_attachment(invoice_id):
    try:
        PermissionService.require_role_at_least("employee")
        invoice = _invoice_for_tenant(invoice_id)
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            raise BadRequest("file is required")
        filename = secure_filename(os.path.basename(upload.filename))[:255]
        extension = os.path.splitext(filename)[1].lower()
        spec = _ALLOWED_ATTACHMENTS.get(extension)
        if not filename or spec is None:
            raise BadRequest("Only PDF, JPG, JPEG and PNG invoice files are supported")
        data = upload.stream.read(10 * 1024 * 1024 + 1)
        if not data:
            raise BadRequest("Uploaded file is empty")
        if len(data) > 10 * 1024 * 1024:
            raise BadRequest("Invoice attachment must not exceed 10 MB")
        mime_type, validate_signature = spec
        if not validate_signature(data):
            raise BadRequest("The file content does not match its extension")
        invoice.attachment_filename = filename
        invoice.attachment_mime_type = mime_type
        invoice.attachment_size = len(data)
        invoice.attachment_data = data
        db.session.commit()
        return jsonify({"success": True, "invoice": invoice.to_dict()}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise


@supplier_invoices_bp.route("/supplier-invoices/<int:invoice_id>/attachment", methods=["GET"])
@login_required
def download_supplier_invoice_attachment(invoice_id):
    try:
        invoice = _invoice_for_tenant(invoice_id)
        if not invoice.attachment_data or not invoice.attachment_filename or not invoice.attachment_mime_type:
            raise NotFound("No attachment is stored for this invoice")
        return send_file(
            BytesIO(invoice.attachment_data),
            mimetype=invoice.attachment_mime_type,
            as_attachment=True,
            download_name=invoice.attachment_filename,
            max_age=0,
        )
    except HTTPException as exc:
        return _error(exc)


@supplier_invoices_bp.route("/supplier-invoices/<int:invoice_id>/reconciliation", methods=["POST"])
@login_required
def save_invoice_reconciliation(invoice_id):
    try:
        PermissionService.require_role_at_least("employee")
        invoice = _invoice_for_tenant(invoice_id)
        order = db.session.scalar(select(Order).where(
            Order.id == invoice.order_id, Order.tenant_id == current_user.tenant_id
        ))
        if order is None:
            raise NotFound("Order not found")
        payload = request.get_json(silent=True) or {}
        submitted_lines = payload.get("lines")
        if not isinstance(submitted_lines, list):
            raise BadRequest("lines must be a list")
        if len(submitted_lines) > 500:
            raise BadRequest("Too many invoice lines")
        order_lines = order.items if isinstance(order.items, list) else []
        saved = []
        seen = set()
        for line in submitted_lines:
            if not isinstance(line, dict):
                raise BadRequest("Each line must be an object")
            index = line.get("order_index")
            if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(order_lines):
                raise BadRequest("Invalid order line index")
            if index in seen:
                raise BadRequest("Duplicate order line index")
            seen.add(index)
            source = order_lines[index] if isinstance(order_lines[index], dict) else {}
            try:
                ordered_qty = Decimal(str(source.get("quantity", 0)))
                ordered_price = Decimal(str(source.get("unit_price", 0)))
                invoiced_qty = Decimal(str(line.get("invoiced_quantity")))
                invoiced_price = Decimal(str(line.get("invoiced_unit_price")))
            except (InvalidOperation, TypeError, ValueError):
                raise BadRequest("Quantities and prices must be valid numbers")
            values = (ordered_qty, ordered_price, invoiced_qty, invoiced_price)
            if any(not value.is_finite() or value < 0 or value > Decimal("999999999.99") for value in values):
                raise BadRequest("Quantities and prices must be non-negative and within the supported limit")
            qty_diff = invoiced_qty - ordered_qty
            price_diff = invoiced_price - ordered_price
            amount_diff = (invoiced_qty * invoiced_price) - (ordered_qty * ordered_price)
            saved.append({
                "order_index": index,
                "product_name": str(source.get("product_name") or source.get("name") or f"פריט {index + 1}")[:500],
                "sku": str(source.get("sku") or "")[:120] or None,
                "ordered_quantity": float(ordered_qty),
                "invoiced_quantity": float(invoiced_qty),
                "ordered_unit_price": float(ordered_price),
                "invoiced_unit_price": float(invoiced_price),
                "quantity_difference": float(qty_diff),
                "unit_price_difference": float(price_diff),
                "amount_difference": float(amount_diff),
            })
        invoice.line_comparison = saved
        db.session.commit()
        return jsonify({"success": True, "invoice": invoice.to_dict()}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
