from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException

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
