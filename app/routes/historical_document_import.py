from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.models.historical_document_import import HistoricalDocumentRecord, HistoricalImportBatch, HistoricalPurchaseOrder
from app.models.order import Order
from app.models.receipt import Receipt
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


historical_document_import_bp = Blueprint(
    "historical_document_import", __name__, url_prefix="/api/historical-document-import"
)


def _error(exc):
    return jsonify({"success": False, "error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code


def _batch(batch_id, lock=False):
    query = select(HistoricalImportBatch).where(
        HistoricalImportBatch.id == batch_id,
        HistoricalImportBatch.tenant_id == current_user.tenant_id,
    )
    if lock:
        query = query.with_for_update()
    row = db.session.scalar(query)
    if row is None:
        raise NotFound("Historical import batch not found")
    return row


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed.quantize(Decimal("0.01"))


def _norm(value):
    return " ".join(str(value or "").casefold().split())


def _supplier_from_extraction(data):
    supplier = data.get("supplier") if isinstance(data.get("supplier"), dict) else {}
    sections = data.get("supplier_sections") if isinstance(data.get("supplier_sections"), list) else []
    matching = data.get("supplier_matching")
    if isinstance(matching, list):
        matching = matching[0] if len(matching) == 1 else None
    supplier_id = matching.get("supplier_id") if isinstance(matching, dict) and matching.get("decision") == "AUTO_MATCH" else None
    supplier_name = supplier.get("name") or ""
    if not supplier_name and len(sections) == 1 and isinstance(sections[0], dict):
        section_supplier = sections[0].get("supplier") if isinstance(sections[0].get("supplier"), dict) else {}
        supplier_name = section_supplier.get("name") or ""
        section_match = sections[0].get("supplier_matching")
        if supplier_id is None and isinstance(section_match, dict) and section_match.get("decision") == "AUTO_MATCH":
            supplier_id = section_match.get("supplier_id")
    if len(sections) > 1:
        supplier_name = supplier_name or ""
        supplier_id = None
    return str(supplier_name).strip() or None, supplier_id if isinstance(supplier_id, int) and not isinstance(supplier_id, bool) else None, len(sections) > 1


def _duplicate_candidate(tenant_id, document_type, document_number, supplier_id, supplier_name):
    if not document_number:
        return None
    if document_type == "INVOICE" and supplier_id:
        existing = db.session.scalar(select(SupplierInvoice).where(
            SupplierInvoice.tenant_id == tenant_id,
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.invoice_number == document_number,
        ).limit(1))
        if existing:
            return {"kind": "supplier_invoice", "id": existing.id}
    if document_type == "DELIVERY_NOTE":
        query = select(Receipt).join(Order, Order.id == Receipt.order_id).where(
            Receipt.tenant_id == tenant_id,
            Order.tenant_id == tenant_id,
            Receipt.receipt_number == document_number,
        )
        if supplier_id:
            query = query.where(Order.supplier_id == supplier_id)
        existing = db.session.scalar(query.limit(1))
        if existing:
            return {"kind": "receipt", "id": existing.id}
    candidates = db.session.scalars(select(HistoricalDocumentRecord).where(
        HistoricalDocumentRecord.tenant_id == tenant_id,
        HistoricalDocumentRecord.document_type == document_type,
        HistoricalDocumentRecord.document_number == document_number,
    )).all()
    for candidate in candidates:
        if supplier_id and candidate.supplier_id:
            if supplier_id == candidate.supplier_id:
                return {"kind": "historical_document", "id": candidate.id}
        elif _norm(supplier_name) and _norm(supplier_name) == _norm(candidate.supplier_name):
            return {"kind": "historical_document", "id": candidate.id}
    return None


@historical_document_import_bp.route("/batches", methods=["GET"])
@login_required
def list_batches():
    try:
        PermissionService.require_role_at_least("manager")
        rows = db.session.scalars(select(HistoricalImportBatch).where(
            HistoricalImportBatch.tenant_id == current_user.tenant_id
        ).order_by(HistoricalImportBatch.created_at.desc(), HistoricalImportBatch.id.desc()).limit(100)).all()
        return jsonify({"success": True, "batches": [row.to_dict() for row in rows]})
    except HTTPException as exc:
        return _error(exc)


@historical_document_import_bp.route("/batches", methods=["POST"])
@login_required
def create_batch():
    try:
        PermissionService.require_role_at_least("manager")
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            name = f"ייבוא היסטורי {date.today().isoformat()}"
        if len(name) > 200:
            raise BadRequest("Batch name must not exceed 200 characters")
        row = HistoricalImportBatch(
            tenant_id=current_user.tenant_id,
            name=name,
            status="review",
            created_by=current_user.id,
        )
        db.session.add(row)
        db.session.flush()
        AuditService.log_event(current_user.tenant_id, current_user.id, "historical_import.batch_created",
            f"Historical document import batch {row.id} created", {"batch_id": row.id, "name": row.name})
        db.session.commit()
        return jsonify({"success": True, "batch": row.to_dict(include_documents=True)}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)


@historical_document_import_bp.route("/batches/<int:batch_id>", methods=["GET"])
@login_required
def get_batch(batch_id):
    try:
        PermissionService.require_role_at_least("manager")
        row = _batch(batch_id)
        return jsonify({"success": True, "batch": row.to_dict(include_documents=True)})
    except HTTPException as exc:
        return _error(exc)


@historical_document_import_bp.route("/batches/<int:batch_id>/documents", methods=["POST"])
@login_required
def add_document(batch_id):
    try:
        PermissionService.require_role_at_least("manager")
        batch = _batch(batch_id, lock=True)
        if batch.status == "finalized":
            raise Conflict("Finalized historical import batches are read-only")
        payload = request.get_json(silent=True) or {}
        analysis_id = payload.get("analysis_id")
        if not isinstance(analysis_id, int) or isinstance(analysis_id, bool) or analysis_id <= 0:
            raise BadRequest("analysis_id must be a positive integer")
        analysis = db.session.scalar(select(DocumentAnalysis).where(
            DocumentAnalysis.id == analysis_id,
            DocumentAnalysis.tenant_id == current_user.tenant_id,
        ))
        if analysis is None:
            raise NotFound("Document analysis not found")
        if analysis.status not in {"ANALYZED", "PARTIALLY_APPLIED", "APPLIED"} or not isinstance(analysis.extracted_data, dict):
            raise Conflict("The document must be successfully analyzed before historical import")
        if analysis.storage_path:
            raise Conflict("The temporary original file has not been cleared yet; wait for analysis cleanup")
        existing_in_batch = db.session.scalar(select(HistoricalDocumentRecord.id).where(
            HistoricalDocumentRecord.tenant_id == current_user.tenant_id,
            HistoricalDocumentRecord.batch_id == batch.id,
            HistoricalDocumentRecord.analysis_id == analysis.id,
        ))
        if existing_in_batch:
            raise Conflict("This analyzed document is already included in the batch")
        data = analysis.extracted_data
        document_type = str(data.get("document_type") or analysis.document_type or "").strip().upper()
        aliases = {"DELIVERY NOTE": "DELIVERY_NOTE", "DELIVERY-NOTE": "DELIVERY_NOTE", "INVOICE": "INVOICE", "DELIVERY_NOTE": "DELIVERY_NOTE"}
        document_type = aliases.get(document_type, document_type)
        if document_type not in {"INVOICE", "DELIVERY_NOTE"}:
            raise BadRequest("Only supplier invoices and delivery notes can be added to a historical batch")
        supplier_name, supplier_id, multi_supplier = _supplier_from_extraction(data)
        if multi_supplier:
            raise BadRequest("This document contains multiple supplier sections. Split it into separate single-supplier documents before historical import.")
        if supplier_id:
            supplier = db.session.scalar(select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.tenant_id == current_user.tenant_id,
            ))
            if supplier is None:
                supplier_id = None
        reasons = []
        if not supplier_name:
            reasons.append("supplier_not_identified")
        if not data.get("document_number"):
            reasons.append("document_number_missing")
        if not _date(data.get("document_date")):
            reasons.append("document_date_missing_or_invalid")
        if not isinstance(data.get("items"), list) or not data.get("items"):
            reasons.append("no_line_items_extracted")
        document_number = str(data.get("document_number") or "").strip() or None
        duplicate = _duplicate_candidate(current_user.tenant_id, document_type, document_number, supplier_id, supplier_name)
        if duplicate:
            reasons.append("possible_duplicate")
        order_reference = str(payload.get("order_reference") or "").strip()[:160] or None
        if not order_reference:
            reasons.append("historical_order_reference_not_set")
        record = HistoricalDocumentRecord(
            tenant_id=current_user.tenant_id,
            batch_id=batch.id,
            analysis_id=analysis.id,
            document_type=document_type,
            source_filename=str(analysis.filename or "")[:255] or None,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            document_number=document_number,
            document_date=_date(data.get("document_date")),
            currency=str(data.get("currency") or "ILS").upper()[:3],
            total_amount=_decimal((data.get("totals") or {}).get("total") if isinstance(data.get("totals"), dict) else None),
            extracted_data=data,
            order_reference=order_reference,
            needs_review=bool(reasons),
            review_reasons=reasons,
            duplicate_of_id=duplicate["id"] if duplicate and duplicate["kind"] == "historical_document" else None,
            created_by=current_user.id,
        )
        db.session.add(record)
        db.session.flush()
        AuditService.log_event(current_user.tenant_id, current_user.id, "historical_import.document_added",
            f"Document added to historical import batch {batch.id}",
            {"batch_id": batch.id, "document_id": record.id, "analysis_id": analysis.id, "document_type": document_type,
             "document_number": document_number, "duplicate_candidate": duplicate})
        db.session.commit()
        return jsonify({"success": True, "document": record.to_dict(), "duplicate_candidate": duplicate}), 201
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except IntegrityError:
        db.session.rollback()
        return _error(Conflict("This analyzed document is already included in the batch"))


@historical_document_import_bp.route("/batches/<int:batch_id>/documents/<int:document_id>", methods=["PATCH"])
@login_required
def review_document(batch_id, document_id):
    try:
        PermissionService.require_role_at_least("manager")
        batch = _batch(batch_id, lock=True)
        if batch.status == "finalized":
            raise Conflict("Finalized historical import batches are read-only")
        record = db.session.scalar(select(HistoricalDocumentRecord).where(
            HistoricalDocumentRecord.id == document_id,
            HistoricalDocumentRecord.batch_id == batch.id,
            HistoricalDocumentRecord.tenant_id == current_user.tenant_id,
        ).with_for_update())
        if record is None:
            raise NotFound("Historical document not found")
        before = {
            "supplier_id": record.supplier_id,
            "supplier_name": record.supplier_name,
            "document_number": record.document_number,
            "document_date": record.document_date.isoformat() if record.document_date else None,
            "order_reference": record.order_reference,
            "needs_review": record.needs_review,
            "review_reasons": list(record.review_reasons or []),
        }
        payload = request.get_json(silent=True) or {}
        original_supplier_name = record.supplier_name
        supplier_name = str(payload.get("supplier_name") or record.supplier_name or "").strip()
        supplier_id = payload.get("supplier_id", record.supplier_id)
        if "supplier_name" in payload and "supplier_id" not in payload and _norm(supplier_name) != _norm(original_supplier_name):
            record.supplier_id = None
        if supplier_id not in (None, ""):
            if not isinstance(supplier_id, int) or isinstance(supplier_id, bool):
                raise BadRequest("supplier_id must be an integer")
            supplier = db.session.scalar(select(Supplier).where(
                Supplier.id == supplier_id, Supplier.tenant_id == current_user.tenant_id
            ))
            if supplier is None:
                raise BadRequest("Supplier does not belong to this organization")
            supplier_name = supplier.name
            record.supplier_id = supplier.id
        elif payload.get("supplier_id") == "":
            record.supplier_id = None
        if len(supplier_name) > 255:
            raise BadRequest("supplier_name must not exceed 255 characters")
        record.supplier_name = supplier_name or None
        if "document_number" in payload:
            record.document_number = str(payload.get("document_number") or "").strip()[:160] or None
        if "document_date" in payload:
            record.document_date = _date(payload.get("document_date"))
        if "total_amount" in payload:
            record.total_amount = _decimal(payload.get("total_amount"))
        if "currency" in payload:
            currency = str(payload.get("currency") or "").upper().strip()
            if currency and (len(currency) != 3 or not currency.isalpha()):
                raise BadRequest("currency must be a three-letter code")
            if currency:
                record.currency = currency
        if "order_reference" in payload:
            record.order_reference = str(payload.get("order_reference") or "").strip()[:160] or None
        confirm_duplicate = payload.get("confirm_duplicate") is True
        reasons = list(record.review_reasons or [])
        if record.supplier_name:
            reasons = [reason for reason in reasons if reason != "supplier_not_identified"]
        elif "supplier_not_identified" not in reasons:
            reasons.append("supplier_not_identified")
        if record.document_number:
            reasons = [reason for reason in reasons if reason != "document_number_missing"]
        elif "document_number_missing" not in reasons:
            reasons.append("document_number_missing")
        if record.document_date:
            reasons = [reason for reason in reasons if reason != "document_date_missing_or_invalid"]
        elif "document_date_missing_or_invalid" not in reasons:
            reasons.append("document_date_missing_or_invalid")
        if record.order_reference:
            reasons = [reason for reason in reasons if reason != "historical_order_reference_not_set"]
        elif "historical_order_reference_not_set" not in reasons:
            reasons.append("historical_order_reference_not_set")
        if confirm_duplicate:
            reasons = [reason for reason in reasons if reason != "possible_duplicate"]
        if payload.get("confirm_extraction") is True:
            reasons = [reason for reason in reasons if reason != "no_line_items_extracted"]
        record.review_reasons = reasons
        record.needs_review = bool(reasons)
        after = {
            "supplier_id": record.supplier_id,
            "supplier_name": record.supplier_name,
            "document_number": record.document_number,
            "document_date": record.document_date.isoformat() if record.document_date else None,
            "order_reference": record.order_reference,
            "needs_review": record.needs_review,
            "review_reasons": reasons,
        }
        AuditService.log_event(current_user.tenant_id, current_user.id, "historical_import.document_reviewed",
            f"Historical document {record.id} reviewed", {"batch_id": batch.id, "document_id": record.id,
            "before": before, "after": after, "confirm_duplicate": confirm_duplicate})
        db.session.commit()
        return jsonify({"success": True, "document": record.to_dict()})
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)


@historical_document_import_bp.route("/batches/<int:batch_id>/finalize", methods=["POST"])
@login_required
def finalize_batch(batch_id):
    try:
        PermissionService.require_role_at_least("manager")
        batch = _batch(batch_id, lock=True)
        if batch.status == "finalized":
            return jsonify({"success": True, "batch": batch.to_dict(include_documents=True), "already_finalized": True})
        records = db.session.scalars(select(HistoricalDocumentRecord).where(
            HistoricalDocumentRecord.tenant_id == current_user.tenant_id,
            HistoricalDocumentRecord.batch_id == batch.id,
        ).order_by(HistoricalDocumentRecord.id.asc()).with_for_update()).all()
        if not records:
            raise Conflict("Add at least one analyzed invoice or delivery note before finalizing")
        unresolved = [record.id for record in records if record.needs_review or not record.supplier_name or not record.document_number or not record.document_date or not record.order_reference]
        if unresolved:
            raise Conflict("Some documents still require review; resolve supplier, date/number, possible duplicates and order reference before finalizing")
        groups = {}
        for record in records:
            key = (_norm(record.supplier_name), _norm(record.order_reference))
            groups.setdefault(key, []).append(record)
        orders = []
        for _, docs in groups.items():
            first = docs[0]
            invoice_totals = [Decimal(str(doc.total_amount)) for doc in docs if doc.document_type == "INVOICE" and doc.total_amount is not None]
            total = sum(invoice_totals, Decimal("0")).quantize(Decimal("0.01")) if invoice_totals else None
            dates = [doc.document_date for doc in docs if doc.document_date]
            order = HistoricalPurchaseOrder(
                tenant_id=current_user.tenant_id,
                batch_id=batch.id,
                supplier_id=first.supplier_id,
                supplier_name=first.supplier_name or "ספק לא מזוהה",
                order_reference=first.order_reference,
                order_date=min(dates) if dates else None,
                currency=first.currency or "ILS",
                total_amount=total,
                items=[
                    {"source_document_id": doc.id, "document_type": doc.document_type,
                     "description": item.get("description"), "quantity": item.get("quantity"),
                     "unit": item.get("unit"), "unit_price": item.get("unit_price"),
                     "discount": item.get("discount"), "tax": item.get("tax")}
                    for doc in docs
                    for item in (doc.extracted_data.get("items") if isinstance(doc.extracted_data, dict) and isinstance(doc.extracted_data.get("items"), list) else [])
                ],
                source_document_ids=[doc.id for doc in docs],
                created_by=current_user.id,
            )
            db.session.add(order)
            db.session.flush()
            for doc in docs:
                doc.historical_order_id = order.id
            orders.append(order)
        batch.status = "finalized"
        batch.finalized_by = current_user.id
        batch.finalized_at = datetime.now(timezone.utc)
        AuditService.log_event(current_user.tenant_id, current_user.id, "historical_import.batch_finalized",
            f"Historical import batch {batch.id} finalized",
            {"batch_id": batch.id, "document_count": len(records), "historical_order_ids": [order.id for order in orders]})
        db.session.commit()
        return jsonify({"success": True, "batch": batch.to_dict(include_documents=True), "orders": [order.to_dict() for order in orders]}), 200
    except HTTPException as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
