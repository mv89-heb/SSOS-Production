"""Provider-agnostic optional AI service for SSOS.

The application must never depend on an AI provider being available. This
module exposes a small interface that returns a deterministic unavailable
result when AI is disabled or not configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AIResult:
    success: bool
    text: str | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None


class AIProvider(Protocol):
    name: str

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> AIResult:
        ...


class UnavailableAIProvider:
    name = "none"

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> AIResult:
        return AIResult(
            success=False,
            error="ai_unavailable",
            provider=self.name,
        )


class AIService:
    """Facade used by business services; provider selection stays centralized."""

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or UnavailableAIProvider()

    @classmethod
    def from_config(cls, config: Any) -> "AIService":
        ai_enabled = bool(config.get("AI_ENABLED", False))
        provider_name = (config.get("AI_PROVIDER") or "gemini").strip().lower()

        if not ai_enabled:
            return cls()

        if provider_name == "gemini":
            from app.services.gemini_provider import GeminiProvider

            return cls(GeminiProvider.from_config(config))

        return cls()

    def is_available(self) -> bool:
        return not isinstance(self.provider, UnavailableAIProvider)

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> AIResult:
        if not prompt or not prompt.strip():
            return AIResult(success=False, error="empty_prompt", provider=self.provider.name)
        return self.provider.generate_text(
            prompt.strip(),
            system_instruction=system_instruction,
        )
