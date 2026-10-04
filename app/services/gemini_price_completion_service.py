"""Gemini-powered web price completion for catalog products."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.extensions import db
from app.models.price_history import PriceHistory
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class GeminiPriceCompletionError(Exception):
    pass


class GeminiPriceCompletionService:
    MAX_SOURCES = 5
    MIN_CONFIDENCE = 45

    def __init__(self, tenant_id: int, user_id: int, config: Any):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.config = config
        self.product_repo = ProductRepository(tenant_id)

    def _client(self):
        api_key = (self.config.get("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise GeminiPriceCompletionError("Gemini API key is not configured")
        from google import genai
        from google.genai import types
        timeout_ms = max(5000, int(float(self.config.get("GEMINI_TIMEOUT", 120)) * 1000))
        return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))

    @staticmethod
    def _number(value):
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        return amount if amount.is_finite() and amount > 0 else None

    @staticmethod
    def _grounding_sources(response):
        sources = []
        try:
            candidates = getattr(response, "candidates", None) or []
            metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
            chunks = getattr(metadata, "grounding_chunks", None) if metadata else None
            for chunk in chunks or []:
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", None) if web else None
                title = getattr(web, "title", None) if web else None
                if uri and str(uri) not in {s["url"] for s in sources}:
                    sources.append({"url": str(uri), "title": str(title or uri)})
                if len(sources) >= GeminiPriceCompletionService.MAX_SOURCES:
                    break
        except Exception:
            logger.exception("Failed to extract Gemini grounding sources")
        return sources

    @staticmethod
    def _schema():
        return {
            "type": "OBJECT",
            "properties": {
                "found": {"type": "BOOLEAN"},
                "price_ils": {"type": "NUMBER"},
                "price_unit": {"type": "STRING"},
                "package_description": {"type": "STRING"},
                "matched_product": {"type": "STRING"},
                "match_type": {"type": "STRING"},
                "matched_supplier": {"type": "STRING"},
                "supplier_match": {"type": "BOOLEAN"},
                "confidence": {"type": "INTEGER"},
                "source_urls": {"type": "ARRAY", "items": {"type": "STRING"}},
                "evidence": {"type": "STRING"},
            },
            "required": ["found", "price_ils", "price_unit", "package_description", "matched_product", "match_type", "matched_supplier", "supplier_match", "confidence", "source_urls", "evidence"],
        }

    def _prompt(self, product):
        return (
            "אתה מנוע השלמת מחירים למערכת רכש ישראלית. מצא מחיר אמיתי ועדכני באינטרנט באמצעות Google Search grounding. "
            "המטרה היא להשלים מחיר חסר, לא להחזיר תשובה כללית.\n\n"
            "כללים: חפש קודם ברקוד אם קיים; אחרת יצרן+שם+משקל/נפח ואז וריאציות שם. העדף מקורות ישראליים ומחיר בשקלים. "
            "המחיר חייב להתאים לאותה יחידת מכירה/אריזה; אל תשווה מארז למחיר יחידה. אל תמציא מחיר או URL. "
            "המחיר שיוזן ל-current_price חייב להיות מחיר של הספק הראשי של המוצר בלבד. חפש מחיר של הספק הראשי או מחירון/אתר רשמי שלו. "
            "אל תשתמש במחיר של קמעונאי או ספק אחר כאילו הוא מחיר הספק הראשי. אם מצאת רק מחיר שוק שאינו של הספק הראשי, החזר found=false ו-supplier_match=false. "
            "matched_supplier חייב להיות שם הספק שממנו מגיע המחיר, ו-supplier_match=true רק כאשר הוא הספק הראשי. "
            "אם אין התאמה מושלמת, מותר להשתמש בהתאמה הקרובה ביותר רק אם ברור שזה אותו מוצר/אריזה, ולציין זאת ולהוריד confidence. "
            "price_ils הוא המחיר עבור האריזה/יחידה שמופיעה במקור. החזר JSON בלבד. אם לא נמצא מחיר אמין, found=false ו-price_ils=0.\n\n"
            f"שם מוצר: {product.name}\n"
            f"תיאור: {product.description or 'לא ידוע'}\n"
            f"ברקוד: {product.barcode or 'לא קיים'}\n"
            f'מק"ט פנימי: {product.sku or "לא קיים"}\n'
            f'מק"ט ספק: {product.supplier_sku or "לא קיים"}\n'
            f"יחידה: {product.unit or 'לא ידוע'}\n"
            f"יחידות בקרטון: {product.units_per_carton or 'לא ידוע'}\n"
            f"קטגוריה: {product.category or 'לא ידועה'}\n"
            f"ספק ראשי: {getattr(getattr(product, 'supplier', None), 'name', None) or 'לא ידוע'}"
        )

    def find_price(self, product):
        from google.genai import types
        client = self._client()
        model = (self.config.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
        fallback = (self.config.get("GEMINI_FALLBACK_MODEL") or "gemini-3.6-flash").strip()
        models = [model] + ([fallback] if fallback and fallback != model else [])
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self._schema(),
            tools=[types.Tool(google_search=types.GoogleSearch())],
            thinking_config=types.ThinkingConfig(thinking_level=(self.config.get("GEMINI_THINKING_LEVEL") or "low").strip()),
        )
        last_error = None
        for model_name in models:
            try:
                response = client.models.generate_content(model=model_name, contents=self._prompt(product), config=config)
                data = json.loads((response.text or "").strip())
                if not isinstance(data, dict):
                    raise GeminiPriceCompletionError("Gemini returned an invalid price object")
                grounded = self._grounding_sources(response)
                urls = [str(u).strip() for u in data.get("source_urls", []) if str(u).strip()]
                for source in grounded:
                    if source["url"] not in urls:
                        urls.append(source["url"])
                data["source_urls"] = urls[: self.MAX_SOURCES]
                data["model"] = model_name
                return data
            except Exception as exc:
                last_error = exc
                logger.exception("Gemini price lookup failed for product %s with %s", product.id, model_name)
                if model_name != models[-1]:
                    continue
        raise GeminiPriceCompletionError(str(last_error)[:500] if last_error else "Gemini price lookup failed")

    @staticmethod
    def _supplier_match(result, product):
        expected = str(getattr(getattr(product, "supplier", None), "name", "") or "").strip().casefold()
        matched = str(result.get("matched_supplier") or "").strip().casefold()
        if not expected or not matched:
            return False
        return bool(result.get("supplier_match")) and (expected in matched or matched in expected)

    def complete_product(self, product):
        result = self.find_price(product)
        confidence = max(0, min(100, int(result.get("confidence") or 0)))
        price = self._number(result.get("price_ils"))
        if not bool(result.get("found")) or price is None:
            return {"status": "unresolved", "product_id": product.id, "product_name": product.name, "confidence": confidence, "reason": str(result.get("evidence") or "לא נמצא מחיר אמין"), "sources": result.get("source_urls") or []}
        if not self._supplier_match(result, product):
            return {"status": "unresolved", "product_id": product.id, "product_name": product.name, "confidence": confidence, "reason": "נמצא מחיר אינטרנטי אך לא ניתן לאמת שהוא המחיר של הספק הראשי של המוצר; המחיר לא הוזן לקטלוג.", "sources": result.get("source_urls") or []}
        if confidence < self.MIN_CONFIDENCE:
            return {"status": "unresolved", "product_id": product.id, "product_name": product.name, "confidence": confidence, "reason": f"רמת הביטחון נמוכה מדי ({confidence}%)", "sources": result.get("source_urls") or []}

        old_price = Decimal(str(product.current_price or 0))
        now = datetime.now(timezone.utc)
        sources = result.get("source_urls") or []
        product.current_price = price
        product.currency = "ILS"
        db.session.add(PriceHistory(
            tenant_id=self.tenant_id, product_id=product.id, supplier_id=product.supplier_id,
            old_price=old_price if old_price > 0 else None, new_price=price, currency="ILS",
            unit=str(result.get("price_unit") or product.unit or "").strip() or None,
            source_type="WEB_GEMINI", effective_at=now, created_at=now,
            source_url=sources[0] if sources else None,
            source_title=str(result.get("matched_product") or "").strip()[:300] or None,
            match_method=str(result.get("match_type") or "WEB_SEARCH").strip()[:50],
            match_confidence=confidence / 100,
        ))
        return {"status": "updated", "product_id": product.id, "product_name": product.name,
                "old_price": float(old_price) if old_price > 0 else None, "new_price": float(price),
                "currency": "ILS", "confidence": confidence, "match_type": result.get("match_type"),
                "package_description": result.get("package_description"), "evidence": result.get("evidence"),
                "sources": sources, "model": result.get("model")}

    def run_batch(self, batch_size=5, product_ids=None):
        batch_size = max(1, min(int(batch_size), 10))
        products = [p for p in self.product_repo.get_all_for_matching() if p.active and (p.current_price is None or Decimal(str(p.current_price or 0)) <= 0)]
        if product_ids:
            wanted = {int(pid) for pid in product_ids}
            batch = [p for p in products if p.id in wanted][:batch_size]
        else:
            batch = products[:batch_size]
        total = len(products)
        results = []
        for product in batch:
            try:
                result = self.complete_product(product)
                db.session.commit()
                if result["status"] == "updated":
                    try:
                        AuditService.log_event(self.tenant_id, self.user_id, "catalog.gemini_price_completed",
                                               f"Gemini completed price for {product.name}",
                                               {"product_id": product.id, "result": result})
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        logger.exception("Price saved but audit event failed for product %s", product.id)
                results.append(result)
            except Exception as exc:
                db.session.rollback()
                logger.exception("Price completion failed for product %s", product.id)
                results.append({"status": "error", "product_id": product.id, "product_name": product.name, "reason": str(exc)[:500]})
        remaining = len([p for p in self.product_repo.get_all_for_matching() if p.active and (p.current_price is None or Decimal(str(p.current_price or 0)) <= 0)])
        return {"total_missing": total, "processed": len(batch), "remaining": remaining,
                "updated": sum(r["status"] == "updated" for r in results),
                "unresolved": sum(r["status"] == "unresolved" for r in results),
                "errors": sum(r["status"] == "error" for r in results), "results": results}
