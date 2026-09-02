"""Gemini implementation of the optional SSOS AI provider."""

from __future__ import annotations

import json
from typing import Any

from app.services.ai_service import AIResult


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when Gemini is enabled")
        from google import genai
        self.model = model
        self._client = genai.Client(api_key=api_key)

    @classmethod
    def from_config(cls, config: Any) -> "GeminiProvider":
        enabled = bool(config.get("GEMINI_ENABLED", False))
        api_key = (config.get("GEMINI_API_KEY") or "").strip()
        model = (config.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
        if not enabled or not api_key:
            raise ValueError("Gemini is not configured")
        return cls(api_key=api_key, model=model)

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> AIResult:
        try:
            contents = prompt
            if system_instruction:
                contents = f"System instruction:\n{system_instruction}\n\nUser request:\n{prompt}"
            response = self._client.models.generate_content(model=self.model, contents=contents)
            text = (response.text or "").strip()
            if not text:
                return AIResult(success=False, error="empty_ai_response", provider=self.name, model=self.model)
            return AIResult(success=True, text=text, provider=self.name, model=self.model)
        except Exception:
            return AIResult(success=False, error="ai_provider_error", provider=self.name, model=self.model)

    def generate_structured_from_file(self, file_path: str, schema: dict, *,
                                      system_instruction: str | None = None) -> AIResult:
        """Extract data from a local document using Gemini structured output.

        The provider returns parsed JSON only. It never receives database
        credentials and has no permission to mutate SSOS state.
        """
        try:
            from google.genai import types
            uploaded = self._client.files.upload(file=file_path)
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
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
            return AIResult(success=False, error="invalid_structured_response", provider=self.name, model=self.model)
        except Exception:
            return AIResult(success=False, error="ai_provider_error", provider=self.name, model=self.model)
