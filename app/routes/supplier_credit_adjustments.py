from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException

from app.extensions import db
from app.models.order import Order
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_credit_adjustment import (
    SupplierCreditAdjustment,
    CREDIT_ADJUSTMENT_ACTIVE,
    CREDIT_ADJUSTMENT_VOIDED,
    VALID_CREDIT_ADJUSTMENT_TYPES,
)
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


supplier_credit_adjustments_bp = Blueprint("supplier_credit_adjustments", __name__, url_prefix="/api")


def _error(exc: HTTPException):
    return jsonify({
        "success": False,
        "error": exc.name.lower().replace(" ", "_"),
        "message": exc.description,
    }), exc.code


def _date(value):
    if value in (None, ""):
        raise BadRequest("adjustment_date is required")
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BadRequest("adjustment_date must be an ISO date (YYYY-MM-DD)")


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise BadRequest("amount must be a valid number")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
        raise BadRequest("amount must be greater than zero and within the supported limit")
    cents = amount.quantize(Decimal("0.01"))
    if amount != cents:
        raise BadRequest("amount must have no more than two decimal places")
    if cents <= 0:
        raise BadRequest("amount must be at least 0.01")
    return cents


def _order_for_tenant(order_id, *, for_update=False):
    stmt = select(Order).where(
        Order.id == order_id,
        Order.tenant_id == current_user.tenant_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    order = db.session.scalar(stmt)
    if order is None:
        raise NotFound("Order not found")
    return order


@supplier_credit_adjustments_bp.route("/orders/<int:order_id>/credit-adjustments", methods=["GET"])
@login_required
def list_order_credit_adjustments(order_id):
    try:
        PermissionService.require_permission("orders.view")
        _order_for_tenant(order_id)
        adjustments = db.session.scalars(
            select(SupplierCreditAdjustment).where(
                SupplierCreditAdjustment.tenant_id == current_user.tenant_id,
                SupplierCreditAdjustment.order_id == order_id,
            ).order_by(
                SupplierCreditAdjustment.adjustment_date.desc(),
                SupplierCreditAdjustment.id.desc(),
            )
        ).all()
        return jsonify({
            "success": True,
            "credit_adjustments": [adjustment.to_dict() for adjustment in adjustments],
        })
    except HTTPException as exc:
        return _error(exc)


@supplier_credit_adjustments_bp.route("/orders/<int:order_id>/credit-adjustments", methods=["POST"])
@login_required
def create_order_credit_adjustment(order_id):
    try:
        PermissionService.require_role_at_least("employee")
        order = _order_for_tenant(order_id, for_update=True)
        if not order.supplier_id:
            raise Conflict("Order must be linked to a supplier before recording a credit adjustment")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("A JSON object is required")

        reference_number = str(data.get("reference_number") or "").strip()
        if not reference_number or len(reference_number) > 120:
            raise BadRequest("reference_number is required (max 120 characters)")
        adjustment_type = str(data.get("adjustment_type") or "").strip()
        if adjustment_type not in VALID_CREDIT_ADJUSTMENT_TYPES:
            raise BadRequest("Unsupported credit adjustment type")

        invoice_id = data.get("invoice_id")
        invoice = None
        if invoice_id not in (None, ""):
            if type(invoice_id) is not int or invoice_id < 1:
                raise BadRequest("invoice_id must be a positive integer")
            invoice = db.session.scalar(select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.tenant_id == current_user.tenant_id,
                SupplierInvoice.order_id == order.id,
                SupplierInvoice.supplier_id == order.supplier_id,
            ))
            if invoice is None:
                raise NotFound("Invoice not found for this order and supplier")

        order_currency = order.currency or "ILS"
        currency = str(data.get("currency") or (invoice.currency if invoice else order_currency) or "ILS").upper().strip()
        if len(currency) != 3 or any(character < "A" or character > "Z" for character in currency):
            raise BadRequest("currency must be a three-letter code")
        expected_currency = invoice.currency if invoice else order_currency
        if currency != expected_currency:
            raise Conflict("Credit adjustment currency must match its linked invoice or order")

        duplicate = db.session.scalar(select(SupplierCreditAdjustment.id).where(
            SupplierCreditAdjustment.tenant_id == current_user.tenant_id,
            SupplierCreditAdjustment.supplier_id == order.supplier_id,
            SupplierCreditAdjustment.reference_number == reference_number,
        ).limit(1))
        if duplicate is not None:
            raise Conflict("Credit adjustment reference already exists for this supplier")

        reason = str(data.get("reason") or "").strip()
        if len(reason) > 2000:
            raise BadRequest("reason must not exceed 2000 characters")

        adjustment = SupplierCreditAdjustment(
            tenant_id=current_user.tenant_id,
            order_id=order.id,
            invoice_id=invoice.id if invoice else None,
            supplier_id=order.supplier_id,
            reference_number=reference_number,
            adjustment_type=adjustment_type,
            adjustment_date=_date(data.get("adjustment_date")),
            amount=_amount(data.get("amount")),
            currency=currency,
            reason=reason or None,
            status=CREDIT_ADJUSTMENT_ACTIVE,
            created_by=current_user.id,
        )
        db.session.add(adjustment)
        db.session.flush()
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_credit_adjustment.created",
            f"Supplier credit adjustment {reference_number} recorded",
            {
                "credit_adjustment_id": adjustment.id,
                "order_id": order.id,
                "invoice_id": invoice.id if invoice else None,
                "supplier_id": order.supplier_id,
                "adjustment_type": adjustment_type,
                "amount": str(adjustment.amount),
                "currency": currency,
            },
        )
        result = adjustment.to_dict()
        db.session.commit()
        return jsonify({"success": True, "credit_adjustment": result}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except IntegrityError as exc:
        db.session.rollback()
        message = str(getattr(exc, "orig", exc))
        constraint_name = getattr(getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", "")
        if constraint_name == "uq_supplier_credit_adjustment_reference" or "UNIQUE constraint failed: supplier_credit_adjustments.tenant_id" in message:
            return _error(Conflict("Credit adjustment reference already exists for this supplier"))
        raise
    except Exception:
        db.session.rollback()
        raise


@supplier_credit_adjustments_bp.route("/supplier-credit-adjustments/<int:adjustment_id>/void", methods=["POST"])
@login_required
def void_supplier_credit_adjustment(adjustment_id):
    try:
        PermissionService.require_role_at_least("manager")
        adjustment = db.session.scalar(select(SupplierCreditAdjustment).where(
            SupplierCreditAdjustment.id == adjustment_id,
            SupplierCreditAdjustment.tenant_id == current_user.tenant_id,
        ).with_for_update())
        if adjustment is None:
            raise NotFound("Supplier credit adjustment not found")
        if adjustment.status == CREDIT_ADJUSTMENT_VOIDED:
            raise Conflict("Credit adjustment is already voided")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("A JSON object is required")
        reason = str(data.get("reason") or "").strip()
        if len(reason) < 3 or len(reason) > 1000:
            raise BadRequest("A void reason between 3 and 1000 characters is required")

        adjustment.status = CREDIT_ADJUSTMENT_VOIDED
        adjustment.voided_at = datetime.now(timezone.utc)
        adjustment.voided_by = current_user.id
        adjustment.void_reason = reason
        AuditService.log_event(
            current_user.tenant_id,
            current_user.id,
            "supplier_credit_adjustment.voided",
            f"Supplier credit adjustment {adjustment.reference_number} voided",
            {
                "credit_adjustment_id": adjustment.id,
                "order_id": adjustment.order_id,
                "supplier_id": adjustment.supplier_id,
                "amount": str(adjustment.amount),
                "currency": adjustment.currency,
                "void_reason": reason,
            },
        )
        result = adjustment.to_dict()
        db.session.commit()
        return jsonify({"success": True, "credit_adjustment": result}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
