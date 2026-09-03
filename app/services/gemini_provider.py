"""Gemini implementation of the optional SSOS AI provider."""

from __future__ import annotations

import io
import json
import logging
import os
import re
from typing import Any

from app.services.ai_service import AIResult

logger = logging.getLogger(__name__)


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
    def _merge_page_results(page_results: list[dict], page_count: int) -> dict:
        """Merge independent page extractions while preserving source page numbers."""
        merged: dict[str, Any] = {
            "items": [],
            "page_count": page_count,
            "pages_processed": 0,
            "extraction_mode": "pdf_page_by_page",
        }
        metadata_keys = ("document_type", "supplier", "document_number", "document_date", "currency")

        for page_number, result in enumerate(page_results, start=1):
            if not isinstance(result, dict):
                continue
            merged["pages_processed"] += 1
            for key in metadata_keys:
                value = result.get(key)
                if value not in (None, "", {}):
                    if key == "supplier" and isinstance(value, dict):
                        existing = merged.get(key) if isinstance(merged.get(key), dict) else {}
                        merged[key] = {**existing, **{k: v for k, v in value.items() if v not in (None, "")}}
                    else:
                        merged[key] = value
            totals = result.get("totals")
            if isinstance(totals, dict) and any(value not in (None, "") for value in totals.values()):
                existing_totals = merged.get("totals") if isinstance(merged.get("totals"), dict) else {}
                merged["totals"] = {
                    **existing_totals,
                    **{key: value for key, value in totals.items() if value not in (None, "")},
                }

            items = result.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized["page_number"] = page_number
                merged["items"].append(normalized)

        return merged

    def _generate_structured_page(
        self,
        page_bytes: bytes,
        page_number: int,
        page_count: int,
        schema: dict,
        system_instruction: str | None,
    ) -> dict:
        """Analyze exactly one PDF page and return its structured extraction."""
        from google.genai import types

        page_instruction = (
            f"This is page {page_number} of {page_count} of the same procurement document. "
            "Analyze this page completely. Extract EVERY product/line item visible on this page, "
            "including rows that continue from a previous page or continue onto the next page. "
            "Do not stop after the first visible row or table section. "
            "Return only facts visible on this page. If there are no line items, return an empty items array."
        )
        instruction = page_instruction
        if system_instruction:
            instruction = f"{system_instruction}\n\n{page_instruction}"
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=instruction,
        )
        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_text(text=f"Extract all procurement data from page {page_number} of {page_count}."),
                types.Part.from_bytes(data=page_bytes, mime_type="application/pdf"),
            ],
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError(f"Gemini returned an empty response for page {page_number}")
        return json.loads(text)

    def generate_structured_from_file(
        self, file_path: str, schema: dict, *, system_instruction: str | None = None
    ) -> AIResult:
        """Extract structured procurement data, processing every PDF page independently."""
        try:
            from google.genai import types

            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction

            if os.path.splitext(file_path)[1].lower() == ".svg":
                with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
                    svg_text = handle.read()
                if not svg_text.strip():
                    return AIResult(success=False, error="empty_svg", provider=self.name, model=self.model)
                prompt = (
                    "Analyze the following SVG/XML procurement document. "
                    "Extract only facts visible in its text/XML content. "
                    "Do not invent missing values.\n\nSVG/XML:\n" + svg_text
                )
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (response.text or "").strip()
                if not text:
                    return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
                data = json.loads(text)
                return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)

            if os.path.splitext(file_path)[1].lower() == ".pdf":
                from pypdf import PdfReader, PdfWriter

                reader = PdfReader(file_path, strict=False)
                page_count = len(reader.pages)
                if page_count <= 0:
                    return AIResult(success=False, error="empty_pdf", provider=self.name, model=self.model)

                page_results: list[dict] = []
                for page_index, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    page_buffer = io.BytesIO()
                    writer.write(page_buffer)
                    writer.close()
                    page_buffer.seek(0)
                    page_results.append(
                        self._generate_structured_page(
                            page_buffer.getvalue(), page_index, page_count, schema, system_instruction
                        )
                    )

                data = self._merge_page_results(page_results, page_count)
                text = json.dumps(data, ensure_ascii=False)
                if data["pages_processed"] != page_count:
                    return AIResult(
                        success=False,
                        text=text,
                        data=data,
                        error=f"pdf_page_coverage_error: processed {data['pages_processed']} of {page_count} pages",
                        provider=self.name,
                        model=self.model,
                    )
                return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)

            uploaded = self._client.files.upload(file=file_path)
            response = self._client.models.generate_content(
                model=self.model,
                contents=[uploaded],
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = (response.text or "").strip()
            if not text:
                return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
            data = json.loads(text)
            return AIResult(success=True, text=text, data=data, provider=self.name, model=self.model)
        except json.JSONDecodeError:
            logger.exception("Gemini returned invalid structured JSON")
            return AIResult(success=False, error="invalid_structured_response", provider=self.name, model=self.model)
        except Exception as exc:
            logger.exception("Gemini structured document analysis failed")
            return AIResult(success=False, error=_safe_provider_error(exc), provider=self.name, model=self.model)
