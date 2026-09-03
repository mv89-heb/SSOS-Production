from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import current_app
from werkzeug.exceptions import BadRequest, NotFound, HTTPException

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.services.ai_service import AIService
from app.services.permission_service import PermissionService
from app.services.price_intelligence_service import PriceIntelligenceService

DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": ["INVOICE", "DELIVERY_NOTE", "PRICE_LIST", "OTHER"]},
        "supplier": {"type": "object", "properties": {"name": {"type": "string"}, "customer_number": {"type": "string"}}},
        "document_number": {"type": "string"}, "document_date": {"type": "string"}, "currency": {"type": "string"},
        "totals": {"type": "object", "properties": {"subtotal": {"type": "number"}, "tax": {"type": "number"}, "total": {"type": "number"}}},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "supplier_sku": {"type": "string"}, "barcode": {"type": "string"}, "description": {"type": "string"},
            "quantity": {"type": "number"}, "unit": {"type": "string"}, "package_quantity": {"type": "number"},
            "unit_price": {"type": "number"}, "discount": {"type": "number"}, "tax": {"type": "number"},
        }}}
    },
    "required": ["document_type", "items"],
}

SYSTEM_INSTRUCTION = """You extract structured procurement data from supplier documents. Return only facts visible in the document. Never invent SKU, barcode, price, supplier or totals. If a value is absent, omit it or use the schema's natural empty value. Preserve decimal numbers exactly as shown. Identify whether the document is an invoice, delivery note, price list, or other document."""


class DocumentIntelligenceService:
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg"}
    ALLOWED_MIMES = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/svg+xml"}

    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def create_analysis(self, filename, storage_path, mime_type):
        PermissionService.require_role_at_least("manager")
        if os.path.splitext(filename)[1].lower() not in self.ALLOWED_EXTENSIONS or mime_type not in self.ALLOWED_MIMES:
            raise BadRequest("Only PDF and supported image documents can be analyzed")
        if not os.path.isfile(storage_path):
            raise BadRequest("Uploaded document is unavailable")
        row = DocumentAnalysis(tenant_id=self.tenant_id, uploaded_by=self.user_id, filename=filename,
                               storage_path=storage_path, mime_type=mime_type, status="UPLOADED")
        db.session.add(row); db.session.commit(); return row

    def _get(self, analysis_id: int):
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).first()
        if row is None: raise NotFound("Document analysis not found")
        return row

    def analyze(self, analysis_id: int):
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status == "APPLIED": return row
        row.status = "PROCESSING"; row.error_message = None; db.session.commit()
        service = AIService.from_config(current_app.config)
        if not service.is_available():
            row.status = "AI_UNAVAILABLE"; row.error_message = "Gemini is disabled or not configured"; db.session.commit(); return row
        result = service.generate_structured_from_file(row.storage_path, DOCUMENT_SCHEMA, system_instruction=SYSTEM_INSTRUCTION)
        row.analyzed_at = datetime.now(timezone.utc); row.provider = result.provider; row.model = result.model
        if not result.success:
            row.status = "FAILED"; row.error_message = result.error or "AI analysis failed"
        elif not isinstance(result.data, dict) or not result.data:
            row.status = "FAILED"; row.error_message = "Structured extraction was empty"
        else:
            row.status = "ANALYZED"; row.document_type = result.data.get("document_type"); row.extracted_data = result.data
        db.session.commit(); return row

    def apply(self, analysis_id: int, lines: list[dict]):
        """Apply only explicitly reviewed mappings; Gemini never mutates catalog state."""
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status == "APPLIED": return row
        if row.status != "ANALYZED" or not isinstance(row.extracted_data, dict): raise BadRequest("Document must be successfully analyzed before apply")
        if not isinstance(lines, list) or not lines: raise BadRequest("lines must contain at least one reviewed mapping")
        intelligence = PriceIntelligenceService(self.tenant_id)
        try:
            for item in lines:
                if not isinstance(item, dict): raise BadRequest("Each reviewed line must be an object")
                product_id, supplier_id, price = item.get("product_id"), item.get("supplier_id"), item.get("price")
                if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0: raise BadRequest("Each reviewed line requires a valid product_id")
                if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0: raise BadRequest("Each reviewed line requires a valid supplier_id")
                supplier = Supplier.query.filter_by(id=supplier_id, tenant_id=self.tenant_id, active=True).first()
                product = Product.query.filter_by(id=product_id, tenant_id=self.tenant_id, active=True).first()
                if supplier is None: raise BadRequest("Supplier does not belong to this tenant or is inactive")
                if product is None: raise BadRequest("Product does not belong to this tenant or is inactive")
                try: price_value = float(price)
                except (TypeError, ValueError): raise BadRequest("Reviewed price must be numeric")
                if price_value <= 0: raise BadRequest("Reviewed price must be greater than zero")
                currency = (item.get("currency") or row.extracted_data.get("currency") or "ILS").upper()
                intelligence.record_observation(product_id=product_id, supplier_id=supplier_id, observed_price=price_value, currency=currency, unit=item.get("unit"), package_quantity=item.get("package_quantity"), source_type=row.document_type or "OTHER", source_document_id=row.id, match_method=item.get("match_method") or "MANUAL_REVIEW", match_confidence=item.get("match_confidence"))
                if not bool(item.get("update_price", False)): continue
                intelligence.accept_price_change(product_id=product_id, supplier_id=supplier_id, new_price=price_value, currency=currency, unit=item.get("unit"), source_type=row.document_type or "OTHER", source_document_id=row.id)
                if supplier_id == product.supplier_id:
                    product.current_price = price_value; product.currency = currency
                    if item.get("unit"): product.unit = item["unit"]
                else:
                    offer = SupplierProductOffer.query.filter_by(tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id).first()
                    if offer is None:
                        offer = SupplierProductOffer(tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id, price=price_value, currency=currency, unit=item.get("unit"), active=True); db.session.add(offer)
                    else:
                        offer.price = price_value; offer.currency = currency
                        if item.get("unit"): offer.unit = item["unit"]
                        offer.active = True
                db.session.flush()
            row.status = "APPLIED"; row.applied_at = datetime.now(timezone.utc); row.applied_by = self.user_id; db.session.commit(); return row
        except HTTPException:
            db.session.rollback(); raise
        except Exception:
            db.session.rollback(); raise

    def get(self, analysis_id: int):
        PermissionService.require_role_at_least("manager")
        return self._get(analysis_id)
