"""Gemini implementation of the optional SSOS AI provider."""

from __future__ import annotations

import io
import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Callable

from app.services.ai_service import AIResult

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]


def _safe_provider_error(exc: Exception) -> str:
    """Return useful provider diagnostics without exposing credentials."""
    detail = str(exc).strip()
    if not detail:
        return "ai_provider_error"
    detail = re.sub(r"(?i)(api[_ -]?key|key)=?[^\s,;]+", r"\1=[REDACTED]", detail)
    detail = detail.replace("GEMINI_API_KEY", "Gemini API key")
    return f"ai_provider_error: {detail[:1500]}"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when Gemini is enabled")
        from google import genai
        self.model = model
        self._client = genai.Client(api_key=api_key)

    @classmethod
    def from_config(cls, config: Any) -> "GeminiProvider":
        enabled = bool(config.get("GEMINI_ENABLED", False))
        api_key = (config.get("GEMINI_API_KEY") or "").strip()
        model = (config.get("GEMINI_MODEL") or "gemini-3.6-flash").strip()
        if not enabled or not api_key:
            raise ValueError("Gemini is not configured")
        return cls(api_key=api_key, model=model)

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> AIResult:
        try:
            contents = prompt if not system_instruction else f"System instruction:\n{system_instruction}\n\nUser request:\n{prompt}"
            response = self._client.models.generate_content(model=self.model, contents=contents)
            text = (response.text or "").strip()
            if not text:
                return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
            return AIResult(success=True, text=text, provider=self.name, model=self.model)
        except Exception as exc:
            logger.exception("Gemini text generation failed")
            return AIResult(success=False, error=_safe_provider_error(exc), provider=self.name, model=self.model)

    @staticmethod
    def _normalize_supplier(value: dict | None) -> tuple[str, str]:
        value = value or {}
        customer = re.sub(r"\W+", "", str(value.get("customer_number") or "").casefold())
        name = re.sub(r"\s+", " ", str(value.get("name") or "").casefold()).strip()
        return customer, name

    @classmethod
    def _same_supplier(cls, left: dict, right: dict) -> bool:
        lc, ln = cls._normalize_supplier(left.get("supplier"))
        rc, rn = cls._normalize_supplier(right.get("supplier"))
        if lc and rc:
            return lc == rc
        if lc or rc or not ln or not rn:
            return False
        return SequenceMatcher(None, ln, rn).ratio() >= 0.90

    @classmethod
    def _merge_page_results(cls, page_results: list[dict], page_count: int) -> dict:
        merged: dict[str, Any] = {
            "items": [],
            "supplier_sections": [],
            "page_count": page_count,
            "pages_processed": 0,
            "extraction_mode": "pdf_page_by_page",
        }
        metadata_keys = ("document_type", "document_number", "document_date", "currency")
        for page_number, result in enumerate(page_results, start=1):
            if not isinstance(result, dict):
                continue
            merged["pages_processed"] += 1
            for key in metadata_keys:
                value = result.get(key)
                if value not in (None, "", {}):
                    merged[key] = value

            raw_sections = result.get("supplier_sections")
            if not isinstance(raw_sections, list) or not raw_sections:
                legacy_supplier = result.get("supplier") if isinstance(result.get("supplier"), dict) else {}
                raw_sections = [{"supplier": legacy_supplier, "items": result.get("items") if isinstance(result.get("items"), list) else []}]

            for raw_section in raw_sections:
                if not isinstance(raw_section, dict):
                    continue
                supplier = raw_section.get("supplier") if isinstance(raw_section.get("supplier"), dict) else {}
                target = next((section for section in merged["supplier_sections"] if cls._same_supplier(section, {"supplier": supplier})), None)
                if target is None:
                    target = {"supplier": dict(supplier), "items": [], "page_numbers": []}
                    merged["supplier_sections"].append(target)
                if page_number not in target["page_numbers"]:
                    target["page_numbers"].append(page_number)
                items = raw_section.get("items") if isinstance(raw_section.get("items"), list) else []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    normalized = dict(item)
                    normalized["page_number"] = page_number
                    normalized["supplier_context"] = dict(supplier)
                    target["items"].append(normalized)
                    merged["items"].append(normalized)

        merged["supplier_sections"] = [section for section in merged["supplier_sections"] if section.get("items") or section.get("supplier")]
        if len(merged["supplier_sections"]) == 1:
            merged["supplier"] = merged["supplier_sections"][0].get("supplier") or {}
        return merged

    def _generate_structured_page(self, page_bytes: bytes, page_number: int, page_count: int, schema: dict, system_instruction: str | None) -> dict:
        from google.genai import types
        page_instruction = (
            f"This is page {page_number} of {page_count} of the same procurement document. Analyze the entire page. "
            "The document may contain multiple suppliers, including multiple suppliers on this SAME page. "
            "Identify EVERY supplier section visible on this page. A supplier section is a group of line items associated "
            "with an explicit supplier name/customer number, a supplier heading, a table heading, or an unambiguous supplier context. "
            "Return one supplier_sections entry per distinct supplier context and put EVERY visible line item into exactly one section. "
            "If a supplier continues from a previous page, use the supplier identity visible on this page when available; do not invent it. "
            "If the supplier cannot be established for a line, place it in a section with an empty supplier object rather than guessing. "
            "Never merge two suppliers merely because their product names are similar. "
            "Extract EVERY product/line item visible on this page, including rows that continue from a previous page or continue onto the next page. "
            "Return only facts visible on this page. If there are no line items, return an empty supplier_sections array."
        )
        instruction = f"{system_instruction}\n\n{page_instruction}" if system_instruction else page_instruction
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, system_instruction=instruction)
        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_text(text=f"Extract all procurement data from page {page_number} of {page_count}, separating all supplier sections."),
                types.Part.from_bytes(data=page_bytes, mime_type="application/pdf"),
            ],
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError(f"Gemini returned an empty response for page {page_number}")
        return json.loads(text)

    def generate_structured_from_file(
        self, file_path: str, schema: dict, *, system_instruction: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> AIResult:
        """Extract structured procurement data and report live progress for PDF pages."""
        try:
            from google.genai import types
            config_kwargs = {"response_mime_type": "application/json", "response_schema": schema}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            if os.path.splitext(file_path)[1].lower() == ".svg":
                if progress_callback:
                    progress_callback({"phase": "processing", "percent": 10, "pages_total": None, "pages_processed": None, "eta_seconds": None})
                with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
                    svg_text = handle.read()
                if not svg_text.strip():
                    return AIResult(success=False, error="empty_svg", provider=self.name, model=self.model)
                prompt = "Analyze the following SVG/XML procurement document. Extract only facts visible in its text/XML content. Do not invent missing values. Separate all distinct supplier sections.\n\nSVG/XML:\n" + svg_text
                response = self._client.models.generate_content(model=self.model, contents=prompt, config=types.GenerateContentConfig(**config_kwargs))
                text = (response.text or "").strip()
                if not text:
                    return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
                data = json.loads(text)
                if progress_callback:
                    progress_callback({"phase": "completed", "percent": 100, "pages_total": None, "pages_processed": None, "eta_seconds": 0})
                return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)

            if os.path.splitext(file_path)[1].lower() == ".pdf":
                from pypdf import PdfReader, PdfWriter
                reader = PdfReader(file_path, strict=False)
                page_count = len(reader.pages)
                if page_count <= 0:
                    return AIResult(success=False, error="empty_pdf", provider=self.name, model=self.model)
                if progress_callback:
                    progress_callback({"phase": "processing", "percent": 0, "pages_total": page_count, "pages_processed": 0, "eta_seconds": None})
                page_results: list[dict] = []
                for page_index, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    page_buffer = io.BytesIO()
                    writer.write(page_buffer)
                    writer.close()
                    page_results.append(self._generate_structured_page(page_buffer.getvalue(), page_index, page_count, schema, system_instruction))
                    processed = page_index
                    percent = round(processed / page_count * 100)
                    if progress_callback:
                        progress_callback({"phase": "processing", "percent": percent, "pages_total": page_count, "pages_processed": processed})
                data = self._merge_page_results(page_results, page_count)
                text = json.dumps(data, ensure_ascii=False)
                if data["pages_processed"] != page_count:
                    return AIResult(success=False, text=text, data=data, error=f"pdf_page_coverage_error: processed {data['pages_processed']} of {page_count} pages", provider=self.name, model=self.model)
                if progress_callback:
                    progress_callback({"phase": "completed", "percent": 100, "pages_total": page_count, "pages_processed": page_count, "eta_seconds": 0})
                return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)

            if progress_callback:
                progress_callback({"phase": "processing", "percent": 10, "pages_total": None, "pages_processed": None, "eta_seconds": None})
            uploaded = self._client.files.upload(file=file_path)
            response = self._client.models.generate_content(model=self.model, contents=[uploaded], config=types.GenerateContentConfig(**config_kwargs))
            text = (response.text or "").strip()
            if not text:
                return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
            data = json.loads(text)
            if progress_callback:
                progress_callback({"phase": "completed", "percent": 100, "pages_total": None, "pages_processed": None, "eta_seconds": 0})
            return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)
        except json.JSONDecodeError:
            logger.exception("Gemini returned invalid structured JSON")
            return AIResult(success=False, error="invalid_structured_response", provider=self.name, model=self.model)
        except Exception as exc:
            logger.exception("Gemini structured document analysis failed")
            return AIResult(success=False, error=_safe_provider_error(exc), provider=self.name, model=self.model)
