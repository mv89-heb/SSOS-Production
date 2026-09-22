from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from flask import current_app
from werkzeug.exceptions import BadRequest, NotFound, HTTPException

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.services.ai_service import AIService
from app.services.catalog_service import CatalogService
from app.services.permission_service import PermissionService
from app.services.price_intelligence_service import PriceIntelligenceService
from app.services.product_matching_service import ProductMatchingService

_SUPPLIER_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "supplier": {"type": "object", "properties": {"name": {"type": "string"}, "customer_number": {"type": "string"}}},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "supplier_sku": {"type": "string"}, "barcode": {"type": "string"}, "description": {"type": "string"},
            "quantity": {"type": "number"}, "unit": {"type": "string"}, "package_quantity": {"type": "number"},
            "unit_price": {"type": "number"}, "discount": {"type": "number"}, "tax": {"type": "number"}, "page_number": {"type": "integer"},
        }}},
    },
}

DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": ["INVOICE", "DELIVERY_NOTE", "PRICE_LIST", "OTHER"]},
        "recipient": {"type": "object", "properties": {"name": {"type": "string"}, "address": {"type": "string"}, "tax_id": {"type": "string"}, "customer_number": {"type": "string"}}},
        "supplier": {"type": "object", "properties": {"name": {"type": "string"}, "customer_number": {"type": "string"}}},
        "supplier_sections": {"type": "array", "items": _SUPPLIER_SECTION_SCHEMA},
        "document_number": {"type": "string"}, "document_date": {"type": "string"}, "currency": {"type": "string"},
        "totals": {"type": "object", "properties": {"subtotal": {"type": "number"}, "tax": {"type": "number"}, "total": {"type": "number"}}},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "supplier_sku": {"type": "string"}, "barcode": {"type": "string"}, "description": {"type": "string"},
            "quantity": {"type": "number"}, "unit": {"type": "string"}, "package_quantity": {"type": "number"},
            "unit_price": {"type": "number"}, "discount": {"type": "number"}, "tax": {"type": "number"},
        }}}
    },
    "required": ["document_type", "items", "supplier_sections"],
}

SYSTEM_INSTRUCTION = """You extract structured procurement data from supplier documents. Return only facts visible in the document. Never invent SKU, barcode, price, supplier or totals. If a value is absent, omit it or use the schema's natural empty value. Never use 0 as a placeholder for a missing price. If a price is visible, extract the actual numeric value exactly as shown; if no price is visible, omit unit_price. Preserve decimal numbers exactly as shown. Identify whether the document is an invoice, delivery note, price list, or other document.

RECIPIENT RULES: Identify the document recipient/customer exactly when visible. For this organization, preserve the visible name and address rather than inferring or normalizing it away.\n\nMULTI-SUPPLIER RULES: A single uploaded document can contain multiple suppliers, including multiple suppliers on one page. You MUST identify every distinct supplier context visible in the document and return one supplier_sections entry for each. Assign every extracted line item to exactly one supplier section. Use explicit supplier names, supplier/customer numbers, table headers, section headers, and unambiguous layout/context. Never assume the whole document belongs to the first supplier you see. Never merge two suppliers just because they sell similar products. If a line's supplier cannot be established from visible evidence, keep that line in a supplier section with an empty supplier object rather than guessing. For a supplier that continues across pages, keep it as the same supplier when the identity is clear."""


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
        row = DocumentAnalysis(tenant_id=self.tenant_id, uploaded_by=self.user_id, filename=filename, storage_path=storage_path, mime_type=mime_type, status="UPLOADED")
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def _delete_temp_file(path):
        if not path:
            return
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            current_app.logger.warning("Could not delete temporary document %s", path, exc_info=True)

    def _finalize_temp_file(self, row):
        path = row.storage_path
        self._delete_temp_file(path)
        row.storage_path = None

    def _get(self, analysis_id: int):
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).first()
        if row is None:
            raise NotFound("Document analysis not found")
        return row

    def analyze(self, analysis_id: int):
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status in {"ANALYZED", "PARTIALLY_APPLIED", "APPLIED"}:
            return row
        if not row.storage_path or not os.path.isfile(row.storage_path):
            row.status = "FAILED"
            row.error_message = "Temporary document is no longer available. Please upload it again."
            self._finalize_temp_file(row)
            db.session.commit()
            return row

        row.status = "PROCESSING"
        row.error_message = None
        row.extracted_data = {"processing": {"phase": "starting", "percent": 0, "pages_total": None, "pages_processed": 0, "elapsed_seconds": 0, "eta_seconds": None}}
        db.session.commit()
        started = time.monotonic()

        def on_progress(progress: dict):
            percent = max(0, min(100, int(progress.get("percent") or 0)))
            total = progress.get("pages_total")
            processed = progress.get("pages_processed") or 0
            elapsed = max(0.0, time.monotonic() - started)
            eta = progress.get("eta_seconds")
            if eta is None and total and processed > 0 and processed < total:
                eta = max(0, round((elapsed / processed) * (total - processed)))
            row.extracted_data = {"processing": {"phase": progress.get("phase", "processing"), "percent": percent, "pages_total": total, "pages_processed": processed, "elapsed_seconds": round(elapsed, 1), "eta_seconds": eta}}
            db.session.commit()

        try:
            service = AIService.from_config(current_app.config)
            if not service.is_available():
                row.status = "AI_UNAVAILABLE"
                row.error_message = "Gemini is disabled or not configured"
                self._finalize_temp_file(row)
                db.session.commit()
                return row

            result = service.generate_structured_from_file(row.storage_path, DOCUMENT_SCHEMA, system_instruction=SYSTEM_INSTRUCTION, progress_callback=on_progress)
            row.analyzed_at = datetime.now(timezone.utc)
            row.provider = result.provider
            row.model = result.model
            if not result.success:
                row.status = "FAILED"
                row.error_message = result.error or "AI analysis failed"
            elif not isinstance(result.data, dict) or not result.data:
                row.status = "FAILED"
                row.error_message = "Structured extraction was empty"
            else:
                enriched = ProductMatchingService(self.tenant_id).enrich_document(result.data)
                row.status = "ANALYZED"
                row.document_type = enriched.get("document_type")
                row.extracted_data = enriched

            self._finalize_temp_file(row)
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            row = self._get(analysis_id)
            row.status = "FAILED"
            row.error_message = str(exc)[:2000]
            self._finalize_temp_file(row)
            db.session.commit()
            raise

    def create_product_from_line(self, analysis_id: int, line_index: int, data: dict | None = None):
        """Create a catalog product from one extracted line and apply that line atomically."""
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status not in {"ANALYZED", "PARTIALLY_APPLIED"} or not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be successfully analyzed before creating a catalog product")
        extracted_items = row.extracted_data.get("items") if isinstance(row.extracted_data.get("items"), list) else []
        if not isinstance(line_index, int) or isinstance(line_index, bool) or line_index < 0 or line_index >= len(extracted_items):
            raise BadRequest("A valid line_index is required")
        applied_indexes = {int(index) for index in (row.extracted_data.get("applied_line_indexes") or []) if str(index).isdigit()}
        if line_index in applied_indexes:
            raise BadRequest("This document line was already applied")
        item = extracted_items[line_index]
        if not isinstance(item, dict):
            raise BadRequest("The selected document line is invalid")
        payload = data if isinstance(data, dict) else {}
        supplier_id = payload.get("supplier_id")
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            supplier_id = (item.get("supplier_matching") or {}).get("supplier_id")
        if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
            raise BadRequest("A supplier must be selected before adding the product")
        supplier = Supplier.query.filter_by(id=supplier_id, tenant_id=self.tenant_id, active=True).first()
        if supplier is None:
            raise BadRequest("Supplier does not belong to this tenant or is inactive")

        name = str(payload.get("name") or item.get("description") or "").strip()
        if not name:
            raise BadRequest("Product name is required")
        supplier_sku = str(
            payload.get("supplier_sku")
            if payload.get("supplier_sku") is not None
            else item.get("supplier_sku") or ""
        ).strip() or None
        barcode = str(
            payload.get("barcode")
            if payload.get("barcode") is not None
            else item.get("barcode") or ""
        ).strip() or None
        unit = str(
            payload.get("unit")
            if payload.get("unit") is not None
            else item.get("unit") or ""
        ).strip() or None

        price_raw = payload.get("current_price") if "current_price" in payload else item.get("unit_price")
        price = 0.0
        if price_raw not in (None, ""):
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                raise BadRequest("Product price must be numeric when provided")
            if price < 0:
                raise BadRequest("Product price cannot be negative")

        package_raw = (
            payload.get("units_per_carton")
            if "units_per_carton" in payload
            else item.get("package_quantity")
        )
        units_per_carton = None
        if package_raw not in (None, ""):
            try:
                package_value = float(package_raw)
            except (TypeError, ValueError):
                raise BadRequest("Units per carton must be numeric when provided")
            if package_value <= 0 or not package_value.is_integer():
                raise BadRequest("Units per carton must be a positive whole number")
            units_per_carton = int(package_value)

        currency = str(payload.get("currency") or row.extracted_data.get("currency") or "ILS").upper()
        product = CatalogService(self.tenant_id, self.user_id).create_product({
            "supplier_id": supplier_id,
            "name": name,
            "description": str(payload.get("description") or item.get("description") or "").strip() or None,
            "current_price": price,
            "currency": currency,
            "barcode": barcode,
            "unit": unit,
            "units_per_carton": units_per_carton,
            "supplier_sku": supplier_sku,
        })
        db.session.flush()
        applied = self.apply(analysis_id, [{
            "line_index": line_index,
            "product_id": product.id,
            "supplier_id": supplier_id,
            "price": price if price > 0 else None,
            "currency": currency,
            "unit": unit,
            "package_quantity": units_per_carton,
            "update_price": price > 0,
            "match_method": "NEW_PRODUCT_FROM_DOCUMENT",
            "match_confidence": 1.0,
        }])
        return applied, product

    def apply(self, analysis_id: int, lines: list[dict]):
        """Apply only explicitly reviewed mappings; Gemini never mutates catalog state."""
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status == "APPLIED":
            return row
        if row.status not in {"ANALYZED", "PARTIALLY_APPLIED"} or not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be successfully analyzed before apply")
        if not isinstance(lines, list) or not lines:
            raise BadRequest("lines must contain at least one reviewed mapping")
        intelligence = PriceIntelligenceService(self.tenant_id)
        extracted_items = row.extracted_data.get("items") if isinstance(row.extracted_data.get("items"), list) else []
        applied_indexes = {int(index) for index in (row.extracted_data.get("applied_line_indexes") or []) if str(index).isdigit()}
        requested_indexes = []
        try:
            for item in lines:
                if not isinstance(item, dict):
                    raise BadRequest("Each reviewed line must be an object")
                line_index = item.get("line_index")
                if not isinstance(line_index, int) or isinstance(line_index, bool) or line_index < 0 or line_index >= len(extracted_items):
                    raise BadRequest("Each reviewed line requires a valid line_index")
                if line_index in applied_indexes or line_index in requested_indexes:
                    raise BadRequest(f"Line {line_index + 1} was already applied or duplicated")
                requested_indexes.append(line_index)
                product_id, supplier_id, price = item.get("product_id"), item.get("supplier_id"), item.get("price")
                if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
                    raise BadRequest("Each reviewed line requires a valid product_id")
                if not isinstance(supplier_id, int) or isinstance(supplier_id, bool) or supplier_id <= 0:
                    raise BadRequest("Each reviewed line requires a valid supplier_id")
                supplier = Supplier.query.filter_by(id=supplier_id, tenant_id=self.tenant_id, active=True).first()
                product = Product.query.filter_by(id=product_id, tenant_id=self.tenant_id, active=True).first()
                if supplier is None:
                    raise BadRequest("Supplier does not belong to this tenant or is inactive")
                if product is None:
                    raise BadRequest("Product does not belong to this tenant or is inactive")
                price_value = None
                if price not in (None, ""):
                    try:
                        parsed_price = float(price)
                    except (TypeError, ValueError):
                        raise BadRequest("Reviewed price must be numeric when provided")
                    if parsed_price > 0:
                        price_value = parsed_price
                currency = (item.get("currency") or row.extracted_data.get("currency") or "ILS").upper()
                if price_value is not None:
                    intelligence.record_observation(product_id=product_id, supplier_id=supplier_id, observed_price=price_value, currency=currency, unit=item.get("unit"), package_quantity=item.get("package_quantity"), source_type=row.document_type or "OTHER", source_document_id=row.id, match_method=item.get("match_method") or "MANUAL_REVIEW", match_confidence=item.get("match_confidence"))
                if not bool(item.get("update_price", False)) or price_value is None:
                    continue
                intelligence.accept_price_change(product_id=product_id, supplier_id=supplier_id, new_price=price_value, currency=currency, unit=item.get("unit"), source_type=row.document_type or "OTHER", source_document_id=row.id)
                if supplier_id == product.supplier_id:
                    product.current_price = price_value
                    product.currency = currency
                    if item.get("unit"):
                        product.unit = item["unit"]
                else:
                    offer = SupplierProductOffer.query.filter_by(tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id).first()
                    if offer is None:
                        offer = SupplierProductOffer(tenant_id=self.tenant_id, product_id=product_id, supplier_id=supplier_id, price=price_value, currency=currency, unit=item.get("unit"), active=True)
                        db.session.add(offer)
                    else:
                        offer.price = price_value
                        offer.currency = currency
                        if item.get("unit"):
                            offer.unit = item["unit"]
                        offer.active = True
                db.session.flush()
            applied_indexes.update(requested_indexes)
            updated_data = dict(row.extracted_data)
            updated_data["applied_line_indexes"] = sorted(applied_indexes)
            row.extracted_data = updated_data
            row.status = "APPLIED" if len(applied_indexes) >= len(extracted_items) else "PARTIALLY_APPLIED"
            row.applied_at = datetime.now(timezone.utc)
            row.applied_by = self.user_id
            db.session.commit()
            return row
        except HTTPException:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise

    def get(self, analysis_id: int):
        PermissionService.require_role_at_least("manager")
        return self._get(analysis_id)
