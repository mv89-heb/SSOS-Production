from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
import os

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoicePayment, INVOICE_APPROVAL_PENDING, INVOICE_APPROVAL_APPROVED, VALID_INVOICE_APPROVAL_STATUSES
from app.models.supplier_offer import SupplierProductOffer
from app.services.audit_service import AuditService
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
    try:
        PermissionService.require_permission("orders.view")
    except HTTPException as exc:
        return _error(exc)
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
        duplicate_invoice = db.session.scalar(select(SupplierInvoice.id).where(
            SupplierInvoice.tenant_id == current_user.tenant_id,
            SupplierInvoice.supplier_id == order.supplier_id,
            SupplierInvoice.invoice_number == invoice_number,
        ).limit(1))
        if duplicate_invoice is not None:
            raise Conflict("Invoice number already exists for this supplier")
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
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_invoice.created",
            f"Supplier invoice {invoice.invoice_number} recorded",
            {
                "invoice_id": invoice.id,
                "order_id": order.id,
                "supplier_id": order.supplier_id,
                "amount": str(invoice.amount),
                "currency": invoice.currency,
            },
        )
        result = invoice.to_dict()
        db.session.commit()
        return jsonify({"success": True, "invoice": result}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except IntegrityError as exc:
        db.session.rollback()
        # The database uniqueness constraint is the final protection against
        # concurrent duplicate invoice submissions.
        original = getattr(exc, "orig", exc)
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", "")
        message = str(original)
        if constraint_name == "uq_supplier_invoice_number" or "UNIQUE constraint failed: supplier_invoices.tenant_id" in message:
            return _error(Conflict("Invoice number already exists for this supplier"))
        raise
    except Exception:
        db.session.rollback()
        raise


@supplier_invoices_bp.route("/supplier-invoices/<int:invoice_id>/approval", methods=["POST"])
@login_required
def update_supplier_invoice_approval(invoice_id):
    try:
        PermissionService.require_role_at_least("manager")
        invoice = db.session.scalar(select(SupplierInvoice).where(
            SupplierInvoice.id == invoice_id,
            SupplierInvoice.tenant_id == current_user.tenant_id,
        ).with_for_update())
        if invoice is None:
            raise NotFound("Supplier invoice not found")
        if invoice.paid_amount > 0:
            raise Conflict("Approval cannot be changed after a payment has been recorded")
        data = request.get_json(silent=True) or {}
        target = str(data.get("approval_status") or "").strip()
        if target not in VALID_INVOICE_APPROVAL_STATUSES:
            raise BadRequest("approval_status must be pending_approval or approved_for_payment")
        note = str(data.get("approval_note") or "").strip()
        if len(note) > 2000:
            raise BadRequest("approval_note must not exceed 2000 characters")
        previous = invoice.approval_status or INVOICE_APPROVAL_PENDING
        invoice.approval_status = target
        invoice.approval_note = note or None
        invoice.approved_by = current_user.id if target == INVOICE_APPROVAL_APPROVED else None
        invoice.approved_at = datetime.now(timezone.utc) if target == INVOICE_APPROVAL_APPROVED else None
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_invoice.approval_changed",
            f"Supplier invoice {invoice.invoice_number} approval changed",
            {
                "invoice_id": invoice.id,
                "order_id": invoice.order_id,
                "previous_status": previous,
                "approval_status": target,
                "approval_note": note or None,
            },
        )
        result = invoice.to_dict()
        db.session.commit()
        return jsonify({"success": True, "invoice": result}), 200
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
        if invoice.approval_status != INVOICE_APPROVAL_APPROVED:
            raise Conflict("Invoice must be approved for payment before recording a payment")
        amount = _amount(data.get("amount"))
        paid = sum((Decimal(str(payment.amount)) for payment in invoice.payments), Decimal("0"))
        if paid + amount > Decimal(str(invoice.amount)):
            raise Conflict("Payment exceeds the outstanding invoice balance")
        payment_date = _date(data.get("payment_date"), "payment_date", required=True)
        payment = SupplierInvoicePayment(
            tenant_id=current_user.tenant_id, invoice_id=invoice.id, amount=amount,
            payment_date=payment_date,
            reference=str(data.get("reference") or "").strip()[:255] or None,
            notes=str(data.get("notes") or "").strip()[:5000] or None,
            created_by=current_user.id,
        )
        # Keep the ORM relationship in sync so the response and subsequent
        # approval checks see the payment created in this transaction.
        invoice.payments.append(payment)
        db.session.add(payment)
        db.session.flush()
        if paid + amount >= Decimal(str(invoice.amount)):
            order = invoice.order
            order_lines = order.items if order and isinstance(order.items, list) else []
            reconciled_lines = invoice.line_comparison if isinstance(invoice.line_comparison, list) else []
            # Only update a supplier offer when its order item can be matched
            # unambiguously to one manually reconciled invoice line.
            for order_item in (order.order_items if order else []):
                offer = order_item.supplier_offer
                if offer is None or offer.tenant_id != current_user.tenant_id or offer.supplier_id != invoice.supplier_id:
                    continue
                product_name = None
                if order_item.product is not None:
                    product_name = getattr(order_item.product, "name", None)
                if not product_name and isinstance(order_item.product_snapshot, dict):
                    product_name = order_item.product_snapshot.get("name") or order_item.product_snapshot.get("product_name")
                if not product_name:
                    continue
                normalized_name = " ".join(str(product_name).casefold().split())
                matching = [
                    line for line in reconciled_lines
                    if isinstance(line, dict)
                    and " ".join(str(line.get("product_name") or "").casefold().split()) == normalized_name
                ]
                if len(matching) == 1:
                    try:
                        paid_unit_price = Decimal(str(matching[0].get("invoiced_unit_price")))
                    except (InvalidOperation, TypeError, ValueError):
                        continue
                    if paid_unit_price.is_finite() and paid_unit_price >= 0:
                        offer.last_paid_price = paid_unit_price.quantize(Decimal("0.01"))
                        offer.last_paid_at = datetime.combine(payment_date, datetime.min.time(), tzinfo=timezone.utc)
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_invoice.payment_recorded",
            f"Payment recorded for supplier invoice {invoice.invoice_number}",
            {
                "invoice_id": invoice.id,
                "payment_id": payment.id,
                "order_id": invoice.order_id,
                "amount": str(amount),
                "currency": invoice.currency,
                "payment_date": payment_date.isoformat(),
                "fully_paid": paid + amount >= Decimal(str(invoice.amount)),
            },
        )
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
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
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
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_invoice.attachment_uploaded",
            f"Attachment uploaded for supplier invoice {invoice.invoice_number}",
            {
                "invoice_id": invoice.id,
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(data),
            },
        )
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
        PermissionService.require_permission("orders.view")
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
        # Receipt quantities are sourced from posted receipt rows only. If an
        # old JSON order line cannot be matched unambiguously to a relational
        # OrderItem, keep received quantity unknown rather than showing a false zero.
        relational_lines = db.session.scalars(
            select(OrderItem)
            .where(OrderItem.tenant_id == current_user.tenant_id, OrderItem.order_id == order.id)
            .order_by(OrderItem.id.asc())
        ).all()
        order_item_by_index = {}
        for order_index, source_line in enumerate(order_lines):
            if order_index >= len(relational_lines) or not isinstance(source_line, dict):
                continue
            relational_line = relational_lines[order_index]
            source_product_id = source_line.get("product_id")
            if source_product_id is not None and source_product_id == relational_line.product_id:
                order_item_by_index[order_index] = relational_line
        relational_ids = [item.id for item in order_item_by_index.values()]
        received_by_order_item = {}
        if relational_ids:
            receipt_query = (
                select(ReceiptItem.order_item_id, func.sum(ReceiptItem.quantity))
                .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
                .where(
                    ReceiptItem.tenant_id == current_user.tenant_id,
                    Receipt.tenant_id == current_user.tenant_id,
                    Receipt.order_id == order.id,
                    Receipt.status == RECEIPT_POSTED,
                    ReceiptItem.order_item_id.in_(relational_ids),
                )
            )
            if invoice.receipt_id is not None:
                receipt_query = receipt_query.where(Receipt.id == invoice.receipt_id)
            received_by_order_item = {
                item_id: Decimal(str(quantity or 0))
                for item_id, quantity in db.session.execute(
                    receipt_query.group_by(ReceiptItem.order_item_id)
                ).all()
            }
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
            relational_line = order_item_by_index.get(index)
            received_qty = (
                received_by_order_item.get(relational_line.id, Decimal("0"))
                if relational_line is not None else None
            )
            saved.append({
                "order_index": index,
                "order_item_id": relational_line.id if relational_line is not None else None,
                "received_quantity": float(received_qty) if received_qty is not None else None,
                "received_quantity_difference": float(invoiced_qty - received_qty) if received_qty is not None else None,
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
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_invoice.reconciliation_saved",
            f"Reconciliation saved for supplier invoice {invoice.invoice_number}",
            {
                "invoice_id": invoice.id,
                "order_id": order.id,
                "line_count": len(saved),
                "lines_with_quantity_or_price_difference": sum(
                    1 for line in saved
                    if line["quantity_difference"] != 0 or line["unit_price_difference"] != 0
                ),
            },
        )
        db.session.commit()
        return jsonify({"success": True, "invoice": invoice.to_dict()}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
