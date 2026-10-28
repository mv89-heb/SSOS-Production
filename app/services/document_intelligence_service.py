from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import current_app
from werkzeug.exceptions import BadRequest, Conflict, NotFound, HTTPException

from app.extensions import db
from app.models.document_analysis import DocumentAnalysis
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_offer import SupplierProductOffer
from app.services.receipt_service import ReceiptService
from app.services.audit_service import AuditService
from app.models.product import Product
from app.models.supplier import Supplier
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

SUPPLIER IDENTIFICATION RULES: Supplier identity is a required extraction goal, not an optional guess. Inspect the entire document, especially the issuer/header/logo area, company name, tax/VAT registration number, phone/address, invoice/payment details, and repeated page headers/footers. Extract the company that ISSUED the invoice, delivery note, or price list as supplier; do not confuse it with the recipient/customer (for this organization, often ישיבת אוהבי ירושלים / ראשית), a delivery destination, a bank, a payment processor, or a brand/manufacturer mentioned only in a product description. Prefer the clearest visible legal/trading name and include the visible supplier/customer account number in customer_number when present. Preserve Hebrew spelling and meaningful company suffixes; do not replace a visible supplier name with a guessed catalog name. If the document-level supplier is visible, populate supplier.name even when supplier_sections is also returned. For a single-supplier document, repeat the same identified supplier in the single supplier_sections entry. If the issuer cannot be established from visible evidence, leave supplier.name empty rather than inventing one, and still extract all other fields.\n\nRECIPIENT RULES: Identify the document recipient/customer exactly when visible. Keep supplier and recipient as separate entities. For this organization, preserve the visible name and address rather than inferring or normalizing it away.\n\nMULTI-SUPPLIER RULES: A single uploaded document can contain multiple suppliers, including multiple suppliers on one page. You MUST identify every distinct supplier context visible in the document and return one supplier_sections entry for each. Assign every extracted line item to exactly one supplier section. Use explicit supplier names, supplier/customer numbers, table headers, section headers, and unambiguous layout/context. Never assume the whole document belongs to the first supplier you see. Never merge two suppliers just because they sell similar products. If a line's supplier cannot be established from visible evidence, keep that line in a supplier section with an empty supplier object rather than guessing. For a supplier that continues across pages, keep it as the same supplier when the identity is clear."""


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
        # A previous request can disappear after the row was persisted,
        # leaving the analysis permanently stuck in PROCESSING. An explicit
        # analyze/retry call may restart it once it is stale.
        if row.status == "PROCESSING" and not row.is_stale_processing():
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
            previous_data = row.extracted_data if isinstance(row.extracted_data, dict) else {}
            partial_items = progress.get("partial_items")
            if not isinstance(partial_items, list):
                partial_items = previous_data.get("items") if isinstance(previous_data.get("items"), list) else []
            progress_data = {"phase": progress.get("phase", "processing"), "percent": percent, "pages_total": total, "pages_processed": processed, "elapsed_seconds": round(elapsed, 1), "eta_seconds": eta}
            row.extracted_data = {"processing": progress_data, "items": partial_items} if partial_items else {"processing": progress_data}
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

    def rematch(self, analysis_id: int):
        """Refresh deterministic catalog matches for saved extraction without calling Gemini."""
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status not in {"ANALYZED", "PARTIALLY_APPLIED"} or not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be successfully analyzed before refreshing product matches")
        if not isinstance(row.extracted_data.get("items"), list):
            raise BadRequest("Document has no extracted item lines to rematch")

        # Work from the saved extraction. The original temporary upload is already
        # deleted after analysis, and re-running Gemini would spend API credits.
        refreshed_data = ProductMatchingService(self.tenant_id).enrich_document(dict(row.extracted_data))
        row.extracted_data = refreshed_data
        db.session.commit()
        return row

    def create_product_from_line(self, analysis_id: int, line_index: int, data: dict | None = None):
        """Create a catalog product from one extracted line and apply that line atomically."""
        PermissionService.require_role_at_least("manager")
        # Lock the analysis before checking the applied-line marker. This prevents
        # two concurrent create-product requests for the same line from creating
        # duplicate catalog products before either request records the line as applied.
        row = DocumentAnalysis.query.filter_by(
            tenant_id=self.tenant_id, id=analysis_id
        ).with_for_update().first()
        if row is None:
            raise NotFound("Document analysis not found")
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
        # Serialize application attempts for the same document in PostgreSQL so
        # concurrent requests cannot both pass the applied-line check.
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).with_for_update().first()
        if row is None:
            raise NotFound("Document analysis not found")
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

    def compare_with_order(self, analysis_id: int, order_id: int):
        """Compare an analyzed delivery note/invoice with one tenant-scoped purchase order."""
        PermissionService.require_role_at_least("manager")
        row = self._get(analysis_id)
        if row.status not in {"ANALYZED", "PARTIALLY_APPLIED", "APPLIED"} or not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be analyzed before reconciliation")
        order = Order.query.filter_by(id=order_id, tenant_id=self.tenant_id).first()
        if order is None:
            raise NotFound("Purchase order not found")
        extracted = row.extracted_data
        supplier_match = extracted.get("supplier_matching") if isinstance(extracted.get("supplier_matching"), dict) else {}
        detected_supplier_id = supplier_match.get("supplier_id")
        if detected_supplier_id and order.supplier_id and detected_supplier_id != order.supplier_id:
            supplier_check = "MISMATCH"
        else:
            supplier_check = "MATCH" if detected_supplier_id == order.supplier_id and detected_supplier_id else "REVIEW"
        order_items = list(OrderItem.query.filter_by(tenant_id=self.tenant_id, order_id=order.id).all())
        by_product = {}
        for order_item in order_items:
            by_product.setdefault(order_item.product_id, []).append(order_item)
        lines = []
        for index, item in enumerate(extracted.get("items") if isinstance(extracted.get("items"), list) else []):
            if not isinstance(item, dict):
                continue
            match = item.get("product_matching") if isinstance(item.get("product_matching"), dict) else {}
            best = match.get("best_match") if isinstance(match.get("best_match"), dict) else {}
            product_id = best.get("product_id")
            candidates = by_product.get(product_id, []) if isinstance(product_id, int) else []
            # An order can contain the same product only once in normal creation.
            order_line = candidates[0] if len(candidates) == 1 else None
            confidence = float(best.get("confidence") or 0) if best else 0.0
            if order_line is None:
                lines.append({
                    "line_index": index, "description": item.get("description"),
                    "matched": False, "status": "UNMATCHED",
                    "reason": "לא נמצא פריט חד-משמעי בהזמנה",
                    "extracted_quantity": item.get("quantity"),
                    "extracted_unit_price": item.get("unit_price"),
                    "confidence": confidence,
                })
                continue
            expected_quantity = float(order_line.quantity)
            extracted_quantity = item.get("quantity")
            expected_price = float(order_line.unit_price)
            extracted_price = item.get("unit_price")
            catalog_price = None
            product = order_line.product
            if product is not None:
                if product.supplier_id == order.supplier_id and product.current_price is not None:
                    catalog_price = float(product.current_price)
                else:
                    current_offer = SupplierProductOffer.query.filter_by(
                        tenant_id=self.tenant_id, product_id=product.id,
                        supplier_id=order.supplier_id, active=True
                    ).first()
                    if current_offer is not None:
                        catalog_price = float(current_offer.price)
            try:
                quantity_delta = round(float(extracted_quantity) - expected_quantity, 3) if extracted_quantity is not None else None
            except (TypeError, ValueError):
                quantity_delta = None
            try:
                price_delta = round(float(extracted_price) - expected_price, 2) if extracted_price is not None else None
            except (TypeError, ValueError):
                price_delta = None
            try:
                catalog_price_delta = round(float(extracted_price) - catalog_price, 2) if extracted_price is not None and catalog_price is not None else None
            except (TypeError, ValueError):
                catalog_price_delta = None
            flags = []
            if confidence < 0.93:
                flags.append("MATCH_REVIEW")
            if quantity_delta is None:
                flags.append("QUANTITY_MISSING")
            elif abs(quantity_delta) > 0.001:
                flags.append("QUANTITY_VARIANCE")
            if price_delta is None:
                flags.append("PRICE_MISSING")
            elif abs(price_delta) > 0.01:
                flags.append("PRICE_VARIANCE")
            if catalog_price_delta is not None and abs(catalog_price_delta) > 0.01:
                flags.append("CATALOG_PRICE_VARIANCE")
            if item.get("unit") and order_line.product and order_line.product.unit:
                if ProductMatchingService.normalize(item.get("unit")) != ProductMatchingService.normalize(order_line.product.unit):
                    flags.append("UNIT_VARIANCE")
            lines.append({
                "line_index": index, "description": item.get("description"),
                "matched": True, "status": "MATCH" if not flags else "REVIEW",
                "order_item_id": order_line.id, "product_id": order_line.product_id,
                "product_name": (order_line.product_snapshot or {}).get("name") if isinstance(order_line.product_snapshot, dict) else (order_line.product.name if order_line.product else None),
                "expected_quantity": expected_quantity, "extracted_quantity": extracted_quantity,
                "quantity_delta": quantity_delta, "expected_unit_price": expected_price,
                "extracted_unit_price": extracted_price, "price_delta": price_delta,
                "catalog_unit_price": catalog_price, "catalog_price_delta": catalog_price_delta,
                "currency": item.get("currency") or extracted.get("currency") or order.currency or "ILS",
                "unit": item.get("unit"), "confidence": confidence, "flags": flags,
            })
        result = {
            "order_id": order.id, "order_number": order.order_number,
            "supplier_id": order.supplier_id, "supplier_name": order.supplier_name,
            "supplier_check": supplier_check, "document_type": row.document_type,
            "document_number": extracted.get("document_number"),
            "document_date": extracted.get("document_date"), "lines": lines,
            "unmatched_count": sum(1 for line in lines if not line.get("matched")),
            "review_count": sum(1 for line in lines if line.get("status") == "REVIEW"),
            "compared_at": datetime.now(timezone.utc).isoformat(),
        }
        updated = dict(extracted)
        updated["order_reconciliation"] = result
        row.extracted_data = updated
        db.session.commit()
        return row, result

    def apply_delivery_note(self, analysis_id: int, user):
        """Post a delivery note as a receipt only after all extracted lines map to the chosen order."""
        PermissionService.require_role_at_least("manager")
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).with_for_update().first()
        if row is None:
            raise NotFound("Document analysis not found")
        if not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be analyzed before receiving")
        data = row.extracted_data
        if str(data.get("document_type") or row.document_type or "").upper() != "DELIVERY_NOTE":
            raise BadRequest("Only a scanned delivery note can be posted as a receipt")
        reconciliation = data.get("order_reconciliation")
        if not isinstance(reconciliation, dict):
            raise BadRequest("Compare the delivery note with a purchase order first")
        if reconciliation.get("supplier_check") != "MATCH":
            raise Conflict("Verify the document supplier against the purchase order before posting the delivery note")
        lines = reconciliation.get("lines") if isinstance(reconciliation.get("lines"), list) else []
        if not lines:
            raise BadRequest("The delivery note has no reconciled lines")
        extracted_items = data.get("items") if isinstance(data.get("items"), list) else []
        receipt_quantities = {}
        for line in lines:
            if not isinstance(line, dict) or not line.get("matched") or not isinstance(line.get("order_item_id"), int):
                raise Conflict("Every delivery note line must be matched to an order item before posting")
            index = line.get("line_index")
            if not isinstance(index, int) or index < 0 or index >= len(extracted_items):
                raise BadRequest("Delivery note line mapping is invalid")
            item = extracted_items[index]
            quantity = item.get("quantity") if isinstance(item, dict) else None
            try:
                amount = Decimal(str(quantity))
            except (InvalidOperation, TypeError, ValueError):
                raise Conflict(f"Missing or invalid quantity on delivery note line {index + 1}")
            if not amount.is_finite() or amount <= 0:
                raise Conflict(f"Missing or invalid quantity on delivery note line {index + 1}")
            order_item_id = line["order_item_id"]
            receipt_quantities[order_item_id] = receipt_quantities.get(order_item_id, Decimal("0")) + amount
        receipt_items = [{"order_item_id": item_id, "quantity": str(quantity)} for item_id, quantity in sorted(receipt_quantities.items())]
        receipt_number = str(data.get("document_number") or "").strip() or f"SCAN-DN-{analysis_id}"
        receipt_payload = {
            "receipt_number": receipt_number,
            "notes": f"נוצר מסריקת תעודת משלוח: {row.filename}",
            "items": receipt_items,
        }
        receipt, replayed = ReceiptService(self.tenant_id).create_receipt(
            user, reconciliation["order_id"], receipt_payload,
            idempotency_key=f"document-analysis-{analysis_id}-receipt",
        )
        updated = dict(data)
        updated["delivery_note_result"] = {
            "receipt_id": receipt.id, "receipt_number": receipt.receipt_number,
            "replayed": replayed,
        }
        row.extracted_data = updated
        row.status = "PARTIALLY_APPLIED"
        row.applied_at = datetime.now(timezone.utc)
        row.applied_by = self.user_id
        db.session.commit()
        return row, receipt

    def apply_invoice_reconciliation(self, analysis_id: int, payload: dict):
        """Record a scanned invoice and optionally accept only safe, high-confidence price changes."""
        PermissionService.require_role_at_least("manager")
        row = DocumentAnalysis.query.filter_by(tenant_id=self.tenant_id, id=analysis_id).with_for_update().first()
        if row is None:
            raise NotFound("Document analysis not found")
        if not isinstance(row.extracted_data, dict):
            raise BadRequest("Document must be analyzed before recording an invoice")
        data = row.extracted_data
        reconciliation = data.get("order_reconciliation")
        if not isinstance(reconciliation, dict):
            raise BadRequest("Compare the document with a purchase order before recording the invoice")
        if str(data.get("document_type") or row.document_type or "").upper() != "INVOICE":
            raise BadRequest("Only a scanned supplier invoice can be recorded through this action")
        order = Order.query.filter_by(id=reconciliation.get("order_id"), tenant_id=self.tenant_id).first()
        if order is None:
            raise NotFound("Reconciled purchase order not found")
        if reconciliation.get("supplier_check") != "MATCH":
            raise Conflict("Verify the invoice supplier against the purchase order before recording the invoice")
        invoice_number = str(payload.get("invoice_number") or data.get("document_number") or "").strip()
        if not invoice_number or len(invoice_number) > 120:
            raise BadRequest("Invoice number is required")
        currency = str(payload.get("currency") or data.get("currency") or order.currency or "ILS").upper().strip()
        if len(currency) != 3 or not currency.isalpha():
            raise BadRequest("Invoice currency must be a three-letter code")
        try:
            amount = Decimal(str(payload.get("amount") if payload.get("amount") not in (None, "") else (data.get("totals") or {}).get("total")))
        except (InvalidOperation, TypeError, ValueError):
            raise BadRequest("A valid invoice total is required")
        if not amount.is_finite() or amount <= 0:
            raise BadRequest("Invoice total must be greater than zero")
        invoice_date = None
        raw_date = payload.get("invoice_date") or data.get("document_date")
        if raw_date:
            try:
                invoice_date = date.fromisoformat(str(raw_date)[:10])
            except ValueError:
                raise BadRequest("Invoice date must be a valid ISO date")
        duplicate = SupplierInvoice.query.filter_by(
            tenant_id=self.tenant_id, supplier_id=order.supplier_id, invoice_number=invoice_number
        ).first()
        if duplicate:
            raise Conflict("Invoice number already exists for this supplier")
        receipt_id = payload.get("receipt_id")
        if receipt_id not in (None, ""):
            from app.models.receipt import Receipt, RECEIPT_POSTED
            receipt = Receipt.query.filter_by(id=receipt_id, order_id=order.id, tenant_id=self.tenant_id).first()
            if receipt is None or receipt.status != RECEIPT_POSTED:
                raise BadRequest("receipt_id must refer to a posted receipt for the selected order")

        lines = reconciliation.get("lines") if isinstance(reconciliation.get("lines"), list) else []
        invoice_lines = []
        allow_price_updates = payload.get("allow_price_updates") is True
        auto_updated = []
        intelligence = PriceIntelligenceService(self.tenant_id)
        order_item_ids = {line.get("order_item_id") for line in lines if isinstance(line, dict) and line.get("order_item_id")}
        order_items = {
            item.id: item for item in OrderItem.query.filter(
                OrderItem.tenant_id == self.tenant_id, OrderItem.order_id == order.id,
                OrderItem.id.in_(order_item_ids or [-1])
            ).all()
        }
        for line in lines:
            if not isinstance(line, dict):
                continue
            item = data.get("items", [])[line["line_index"]] if isinstance(line.get("line_index"), int) and 0 <= line["line_index"] < len(data.get("items", [])) else {}
            quantity = item.get("quantity") if isinstance(item, dict) else None
            invoice_price = item.get("unit_price") if isinstance(item, dict) else None
            invoice_lines.append({
                **line,
                "invoiced_quantity": quantity,
                "received_quantity": None,
                "invoice_unit_price": invoice_price,
            })
            if not allow_price_updates or not line.get("matched") or line.get("confidence", 0) < 0.93:
                continue
            order_item = order_items.get(line.get("order_item_id"))
            if order_item is None or invoice_price in (None, ""):
                continue
            product = Product.query.filter_by(id=order_item.product_id, tenant_id=self.tenant_id, active=True).first()
            if product is None:
                continue
            extracted_unit = item.get("unit") if isinstance(item, dict) else None
            if not extracted_unit or not product.unit:
                continue
            if ProductMatchingService.normalize(extracted_unit) != ProductMatchingService.normalize(product.unit):
                continue
            line_currency = str(item.get("currency") or data.get("currency") or order.currency or "ILS").upper()
            if line_currency != currency or currency != (order.currency or "ILS").upper():
                continue
            try:
                new_price = Decimal(str(invoice_price))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not new_price.is_finite() or new_price <= 0:
                continue
            if item.get("discount") not in (None, "", 0, 0.0, "0", "0.0"):
                continue
            supplier_id = order.supplier_id
            offer = None
            if supplier_id == product.supplier_id:
                old_price = Decimal(str(product.current_price or 0))
                existing_currency = (product.currency or "ILS").upper()
            else:
                offer = SupplierProductOffer.query.filter_by(
                    tenant_id=self.tenant_id, product_id=product.id, supplier_id=supplier_id, active=True
                ).first()
                # Do not invent a new supplier offer from a single scanned line.
                # Missing offers remain for explicit catalog review.
                if offer is None:
                    continue
                old_price = Decimal(str(offer.price))
                existing_currency = (offer.currency or "ILS").upper()
            if existing_currency != currency or abs(new_price - old_price) <= Decimal("0.01"):
                continue
            intelligence.record_observation(
                product_id=product.id, supplier_id=supplier_id, observed_price=new_price,
                currency=currency, unit=extracted_unit, source_type="INVOICE",
                source_document_id=row.id, match_method="ORDER_RECONCILIATION",
                match_confidence=line.get("confidence"),
            )
            intelligence.accept_price_change(
                product_id=product.id, supplier_id=supplier_id, new_price=new_price,
                currency=currency, unit=extracted_unit, source_type="INVOICE",
                source_document_id=row.id,
            )
            if supplier_id == product.supplier_id:
                product.current_price = new_price
                product.currency = currency
                product.unit = extracted_unit
            else:
                offer.price = new_price
                offer.currency = currency
                offer.unit = extracted_unit
                offer.active = True
            auto_updated.append({
                "product_id": product.id, "product_name": product.name,
                "old_price": float(old_price), "new_price": float(new_price),
                "supplier_id": supplier_id,
            })

        invoice = SupplierInvoice(
            tenant_id=self.tenant_id, order_id=order.id, supplier_id=order.supplier_id,
            receipt_id=int(receipt_id) if receipt_id not in (None, "") else None,
            invoice_number=invoice_number, invoice_date=invoice_date, amount=amount,
            currency=currency, notes="נוצרה מסריקת מסמך; יש להשלים בדיקה ואישור לפי הצורך.",
            approval_status="pending_approval", line_comparison=invoice_lines,
            created_by=self.user_id,
        )
        db.session.add(invoice)
        db.session.flush()
        AuditService.log_event(
            self.tenant_id, self.user_id, "supplier_invoice.scanned",
            f"Supplier invoice {invoice_number} created from document scan",
            {"invoice_id": invoice.id, "order_id": order.id, "document_analysis_id": row.id,
             "automatic_price_updates": auto_updated},
        )
        updated = dict(data)
        updated["invoice_reconciliation_result"] = {
            "invoice_id": invoice.id, "invoice_number": invoice_number,
            "automatic_price_updates": auto_updated, "prices_updated_count": len(auto_updated),
        }
        row.extracted_data = updated
        row.status = "PARTIALLY_APPLIED"
        row.applied_at = datetime.now(timezone.utc)
        row.applied_by = self.user_id
        db.session.commit()
        return row, invoice, auto_updated

    def get(self, analysis_id: int):
        PermissionService.require_role_at_least("manager")
        return self._get(analysis_id)
