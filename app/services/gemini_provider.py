"""Gemini implementation of the optional SSOS AI provider."""

from __future__ import annotations

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

    def generate_structured_from_file(
        self, file_path: str, schema: dict, *, system_instruction: str | None = None
    ) -> AIResult:
        """Extract structured procurement data, treating SVG as XML/text."""
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
            else:
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
