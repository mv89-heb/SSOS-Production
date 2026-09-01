from __future__ import annotations

import mimetypes
import os
from datetime import datetime, timezone

from flask import current_app
from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.services.ai_service import AIService
from app.services.permission_service import PermissionService


DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": ["INVOICE", "DELIVERY_NOTE", "PRICE_LIST", "OTHER"]},
        "supplier": {"type": "object", "properties": {
            "name": {"type": "string"}, "customer_number": {"type": "string"}
        }},
        "document_number": {"type": "string"},
        "document_date": {"type": "string"},
        "currency": {"type": "string"},
        "totals": {"type": "object", "properties": {
            "subtotal": {"type": "number"}, "tax": {"type": "number"}, "total": {"type": "number"}
        }},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "supplier_sku": {"type": "string"}, "barcode": {"type": "string"},
            "description": {"type": "string"}, "quantity": {"type": "number"},
            "unit": {"type": "string"}, "package_quantity": {"type": "number"},
            "unit_price": {"type": "number"}, "discount": {"type": "number"}, "tax": {"type": "number"}
        }}},
    },
    "required": ["document_type", "items"],
}


SYSTEM_INSTRUCTION = """You extract structured procurement data from supplier documents.
Return only facts visible in the document. Never invent SKU, barcode, price,
supplier or totals. If a value is absent, omit it or use the schema's natural
empty value. Preserve decimal numbers exactly as shown. Identify whether the
document is an invoice, delivery note, price list, or other document."""


class DocumentIntelligenceService:
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    ALLOWED_MIMES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}

    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def create_analysis(self, filename: str, storage_path: str, mime_type: str) -> DocumentAnalysis:
        PermissionService.require_role_at_least("manager")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS or mime_type not in self.ALLOWED_MIMES:
            raise BadRequest("Only PDF and supported image documents can be analyzed")
        if not os.path.isfile(storage_path):
            raise BadRequest("Uploaded document is unavailable")
        row = DocumentAnalysis(
            tenant_id=self.tenant_id, uploaded_by=self.user_id,
            filename=filename, storage_path=storage_path, mime_type=mime_type,
            status="UPLOADED",
        )
        db.session.add(row)
        db.session.commit()
        return row

    def analyze(self, analysis_id: int) -> DocumentAnalysis:
        PermissionService.require_role_at_least("manager")
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).first()
        if row is None:
            raise NotFound("Document analysis not found")
        row.status = "PROCESSING"
        row.error_message = None
        db.session.commit()

        service = AIService.from_config(current_app.config)
        if not service.is_available():
            row.status = "AI_UNAVAILABLE"
            row.error_message = "Gemini is disabled or not configured"
            db.session.commit()
            return row

        result = service.generate_structured_from_file(
            row.storage_path, DOCUMENT_SCHEMA, system_instruction=SYSTEM_INSTRUCTION,
        )
        row.analyzed_at = datetime.now(timezone.utc)
        row.provider = result.provider
        row.model = result.model
        if not result.success:
            row.status = "FAILED"
            row.error_message = result.error or "AI analysis failed"
        else:
            data = result.data if isinstance(result.data, dict) else None
            if not data:
                row.status = "FAILED"
                row.error_message = "Structured extraction was empty"
            else:
                row.status = "ANALYZED"
                row.document_type = data.get("document_type")
                row.extracted_data = data
        db.session.commit()
        return row

    def get(self, analysis_id: int) -> DocumentAnalysis:
        PermissionService.require_role_at_least("manager")
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).first()
        if row is None:
            raise NotFound("Document analysis not found")
        return row
