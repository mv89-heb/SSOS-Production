from __future__ import annotations

import json
from datetime import datetime

from flask import current_app


class ReminderAIService:
    """Use Gemini as an advisor, never as the source of truth for scheduling."""

    @classmethod
    def enabled(cls) -> bool:
        return bool(
            current_app.config.get("AI_ENABLED")
            and current_app.config.get("GEMINI_ENABLED")
            and current_app.config.get("GEMINI_API_KEY")
        )

    @classmethod
    def choose_candidate(cls, order, candidates: list[dict], now: datetime) -> dict | None:
        if not cls.enabled() or not candidates:
            return None
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=current_app.config["GEMINI_API_KEY"],
                http_options=types.HttpOptions(
                    timeout=10_000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            payload = {
                "order": {
                    "order_number": order.order_number,
                    "supplier_name": order.supplier_name,
                    "supplier_contact": order.supplier_contact,
                    "supplier_email": order.supplier_email,
                    "status": order.status,
                    "notes": order.notes,
                    "items": order.items or [],
                },
                "now": now.isoformat(),
                "candidates": candidates,
            }
            prompt = (
                "You are the scheduling assistant for a procurement system. "
                "Choose the single best reminder candidate from the supplied list. "
                "Do not invent a date/time and do not return a value that is not in candidates. "
                "Prefer a practical follow-up time that gives the purchaser a chance to act. "
                "Return only JSON with keys candidate_at and reason. The reason must be concise Hebrew.\n\n"
                + json.dumps(payload, ensure_ascii=False, default=str)
            )
            response = client.models.generate_content(
                model=current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "candidate_at": {"type": "STRING"},
                            "reason": {"type": "STRING"},
                        },
                        "required": ["candidate_at", "reason"],
                    },
                ),
            )
            result = json.loads(response.text)
            candidate_at = str(result.get("candidate_at") or "")
            match = next((item for item in candidates if item["at"] == candidate_at), None)
            if not match:
                return None
            return {"at": match["at"], "reason": str(result.get("reason") or "בחירה לפי כללי התזכורות.")[:500]}
        except Exception:
            current_app.logger.exception("Gemini reminder recommendation failed; deterministic scheduling remains active")
            return None
