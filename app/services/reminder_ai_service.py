from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from flask import current_app


class ReminderAIService:
    """Gemini advisor for reminder intent, urgency and recurrence.

    Deterministic rules remain the source of truth for safety and scheduling.
    Gemini can enrich the decision, but it cannot invent a reminder time or
    bypass the hard bounds enforced here.
    """

    URGENCY_THRESHOLDS = ((80, "critical"), (60, "high"), (30, "normal"), (0, "low"))
    DEFAULT_REPEAT_MINUTES = 60
    DEFAULT_ESCALATE_AFTER = 3

    @classmethod
    def enabled(cls) -> bool:
        return bool(current_app.config.get("AI_ENABLED") and current_app.config.get("GEMINI_ENABLED") and current_app.config.get("GEMINI_API_KEY"))

    @staticmethod
    def _text_blob(order, user_text: str = "") -> str:
        items = order.items or []
        item_text = " ".join(str(item.get("description") or item.get("name") or item.get("product_name") or "") for item in items if isinstance(item, dict))
        return " ".join([str(order.notes or ""), str(user_text or ""), item_text, str(order.supplier_name or "")]).casefold()

    @classmethod
    def deterministic_score(cls, order, now: datetime, user_text: str = "", deadline: datetime | None = None) -> int:
        text = cls._text_blob(order, user_text)
        score = 0
        if any(term in text for term in ("דחוף", "קריטי", "חייב", "בהקדם", "היום", "תקוע", "עוצר", "urgent", "critical", "asap")):
            score += 35
        if any(term in text for term in ("עוצר עבודה", "לא יכול לעבוד", "מעכב", "תקלה", "עצירה", "blocked", "blocking")):
            score += 30
        if deadline is not None:
            delta = (deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)) - now
            if delta.total_seconds() <= 3600:
                score += 40
            elif delta.total_seconds() <= 24 * 3600:
                score += 30
            elif delta.total_seconds() <= 72 * 3600:
                score += 15
            if delta.total_seconds() < 0:
                score += 40
        try:
            amount = float(order.final_total or 0)
            if amount >= 20000:
                score += 10
            elif amount >= 10000:
                score += 5
        except (TypeError, ValueError):
            pass
        return min(100, score)

    @classmethod
    def _urgency_label(cls, score: int) -> str:
        for threshold, label in cls.URGENCY_THRESHOLDS:
            if score >= threshold:
                return label
        return "low"

    @classmethod
    def _schema(cls) -> dict:
        return {"type": "OBJECT", "properties": {"urgency": {"type": "STRING", "enum": ["low", "normal", "high", "critical"]}, "score": {"type": "INTEGER", "minimum": 0, "maximum": 100}, "reason": {"type": "STRING"}, "first_reminder_minutes": {"type": "INTEGER", "minimum": 5, "maximum": 10080}, "repeat_minutes": {"type": "INTEGER", "minimum": 5, "maximum": 10080}, "escalate_after_occurrences": {"type": "INTEGER", "minimum": 0, "maximum": 100}}, "required": ["urgency", "score", "reason", "first_reminder_minutes", "repeat_minutes", "escalate_after_occurrences"]}

    @classmethod
    def _call_gemini(cls, payload: dict, schema: dict) -> dict | None:
        if not cls.enabled():
            return None
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=current_app.config["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=int(float(current_app.config.get("GEMINI_TIMEOUT", 30)) * 1000), retry_options=types.HttpRetryOptions(attempts=1)))
            system_instruction = "אתה יועץ תזכורות למערכת רכש. קבע דחיפות ותדירות מעקב על סמך הנתונים בלבד. אל תמציא דדליין או עובדות. אם אין ודאות, העדף תדירות מתונה. התזכורת חייבת להמשיך עד שההזמנה מסומנת טופל. החזר JSON בלבד."
            response = client.models.generate_content(model=current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash"), contents=json.dumps(payload, ensure_ascii=False, default=str), config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, system_instruction=system_instruction))
            return json.loads(response.text or "{}")
        except Exception:
            current_app.logger.exception("Gemini reminder intelligence failed; deterministic rules remain active")
            return None

    @classmethod
    def analyze(cls, order, now: datetime | None = None, user_text: str = "", deadline: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        baseline = cls.deterministic_score(order, now, user_text, deadline)
        payload = {"task": "Assess urgency and reminder strategy for this procurement order.", "order": {"order_number": order.order_number, "supplier_name": order.supplier_name, "status": order.status, "notes": order.notes, "items": order.items or [], "final_total": float(order.final_total or 0)}, "user_text": user_text, "deadline": deadline.isoformat() if deadline else None, "now": now.isoformat(), "deterministic_baseline_score": baseline}
        result = cls._call_gemini(payload, cls._schema())
        try:
            ai_score = int(result.get("score", baseline)) if isinstance(result, dict) else baseline
        except (TypeError, ValueError):
            ai_score = baseline
        score = max(baseline, min(100, ai_score))
        urgency = cls._urgency_label(score)
        reason = str((result or {}).get("reason") or "הערכת דחיפות לפי נתוני ההזמנה וכללי המערכת.")[:500]
        try:
            repeat = int((result or {}).get("repeat_minutes") or cls.DEFAULT_REPEAT_MINUTES)
            first = int((result or {}).get("first_reminder_minutes") or repeat)
            escalate = int((result or {}).get("escalate_after_occurrences") or 0)
        except (TypeError, ValueError):
            repeat, first, escalate = cls.DEFAULT_REPEAT_MINUTES, cls.DEFAULT_REPEAT_MINUTES, cls.DEFAULT_ESCALATE_AFTER
        repeat = max(5, min(10080, repeat))
        first = max(5, min(10080, first))
        escalate = max(0, min(100, escalate))
        if urgency == "critical":
            repeat, escalate = min(repeat, 60), max(escalate, 2)
        elif urgency == "high":
            repeat, escalate = min(repeat, 120), max(escalate, 3)
        elif escalate == 0:
            escalate = cls.DEFAULT_ESCALATE_AFTER
        return {"urgency": urgency, "score": score, "reason": reason, "first_reminder_minutes": first, "repeat_minutes": repeat, "escalate_after_occurrences": escalate, "source": "gemini+rules" if result else "rules", "analyzed_at": now.isoformat()}

    @classmethod
    def choose_candidate(cls, order, candidates: list[dict], now: datetime) -> dict | None:
        if not candidates or not cls.enabled():
            return None
        schema = {"type": "OBJECT", "properties": {"candidate_at": {"type": "STRING"}, "reason": {"type": "STRING"}}, "required": ["candidate_at", "reason"]}
        payload = {"task": "Choose exactly one candidate. Do not invent a date/time.", "order": {"order_number": order.order_number, "supplier_name": order.supplier_name, "status": order.status, "notes": order.notes, "items": order.items or []}, "now": now.isoformat(), "candidates": candidates}
        result = cls._call_gemini(payload, schema)
        if not result:
            return None
        candidate_at = str(result.get("candidate_at") or "")
        match = next((item for item in candidates if item["at"] == candidate_at), None)
        return {"at": match["at"], "reason": str(result.get("reason") or "בחירה לפי כללי התזכורות.")[:500]} if match else None

    @classmethod
    def parse_natural_language(cls, order, text: str, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        text = (text or "").strip()
        if not text:
            raise ValueError("text is required")
        schema = {"type": "OBJECT", "properties": {"first_reminder_minutes": {"type": "INTEGER", "minimum": 5, "maximum": 10080}, "repeat_minutes": {"type": "INTEGER", "minimum": 5, "maximum": 10080}, "escalate_after_occurrences": {"type": "INTEGER", "minimum": 0, "maximum": 100}}, "required": ["first_reminder_minutes", "repeat_minutes", "escalate_after_occurrences"]}
        payload = {"task": "Extract reminder intent from Hebrew text. Return delays only; never invent a calendar date.", "order": {"order_number": order.order_number, "supplier_name": order.supplier_name, "status": order.status, "notes": order.notes}, "current_time": now.isoformat(), "timezone": current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem"), "request": text}
        result = cls._call_gemini(payload, schema)
        analysis = cls.analyze(order, now=now, user_text=text)
        if result:
            first = max(5, min(10080, int(result.get("first_reminder_minutes") or analysis["first_reminder_minutes"])))
            repeat = max(5, min(10080, int(result.get("repeat_minutes") or analysis["repeat_minutes"])))
            escalate = max(0, min(100, int(result.get("escalate_after_occurrences") or analysis["escalate_after_occurrences"])))
        else:
            lower = text.casefold()
            if "חצי שעה" in lower:
                first = 30
            elif "שעתיים" in lower:
                first = 120
            elif "שעה" in lower:
                first = 60
            elif "מחר" in lower:
                first = 1440
            else:
                first = analysis["first_reminder_minutes"]
            repeat, escalate = analysis["repeat_minutes"], analysis["escalate_after_occurrences"]
        return {**analysis, "first_reminder_at": (now + timedelta(minutes=first)).isoformat(), "first_reminder_minutes": first, "repeat_minutes": repeat, "escalate_after_occurrences": escalate, "interpretation": text}

    @classmethod
    def apply_analysis(cls, order, analysis: dict, *, reminder_at: datetime | None = None, mode: str = "ai") -> None:
        now = datetime.now(timezone.utc)
        at = reminder_at or (now + timedelta(minutes=int(analysis["first_reminder_minutes"])))
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        snapshot = dict(order.reminder_rules_snapshot or {})
        snapshot.update({"mode": mode, "ai": analysis, "recurrence": {"every_minutes": int(analysis["repeat_minutes"]), "max_occurrences": 0}, "escalation": {"after_occurrences": int(analysis["escalate_after_occurrences"])}, "occurrences": 0, "escalated": False, "created_at": now.isoformat()})
        order.reminder_rules_snapshot = snapshot
        order.next_reminder_at = at.astimezone(timezone.utc)

    @classmethod
    def urgency_display(cls, urgency: str) -> dict:
        return {"low": {"label": "נמוכה", "emoji": "🟢"}, "normal": {"label": "רגילה", "emoji": "🟡"}, "high": {"label": "גבוהה", "emoji": "🟠"}, "critical": {"label": "קריטית", "emoji": "🔴"}}.get(urgency, {"label": "רגילה", "emoji": "🟡"})
