from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models.google_calendar import GoogleCalendarConnection

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _client_id() -> str:
    return current_app.config.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip()


def _client_secret() -> str:
    return current_app.config.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip()


def is_configured() -> bool:
    return bool(_client_id() and _client_secret())


def redirect_uri() -> str:
    configured = current_app.config.get("GOOGLE_CALENDAR_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return current_app.config.get("API_PUBLIC_URL", "").rstrip("/") + "/api/integrations/google-calendar/callback"


def _fernet() -> Fernet:
    digest = hashlib.sha256(current_app.config["SECRET_KEY"].encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored Google Calendar credentials cannot be decrypted") from exc


def create_oauth_state(user_id: int) -> str:
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="google-calendar-oauth")
    return serializer.dumps({"user_id": user_id, "nonce": secrets.token_urlsafe(16)})


def read_oauth_state(state: str) -> int:
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="google-calendar-oauth")
    try:
        payload = serializer.loads(state, max_age=600)
    except (BadSignature, SignatureExpired) as exc:
        raise ValueError("OAuth state expired or invalid") from exc
    return int(payload["user_id"])


def authorization_url(user_id: int) -> str:
    if not is_configured():
        raise RuntimeError("Google Calendar OAuth is not configured")
    state = create_oauth_state(user_id)
    params = {
        "client_id": _client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": CALENDAR_SCOPE + " openid email",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def _http_json(url: str, *, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> dict:
    payload = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        payload = urllib.parse.urlencode(data).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google API request failed ({exc.code}): {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google API request failed: {exc.reason}") from exc


def exchange_code(code: str) -> dict:
    if not is_configured():
        raise RuntimeError("Google Calendar OAuth is not configured")
    return _http_json(
        GOOGLE_TOKEN_URL,
        method="POST",
        data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
    )


def _access_token(connection: GoogleCalendarConnection) -> str:
    refresh_token = _decrypt(connection.refresh_token_encrypted)
    token = _http_json(
        GOOGLE_TOKEN_URL,
        method="POST",
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("Google did not return an access token")
    return access_token


def _api(connection: GoogleCalendarConnection, path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    token = _access_token(connection)
    url = CALENDAR_API + path
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google Calendar API failed ({exc.code}): {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google Calendar API failed: {exc.reason}") from exc


def get_primary_calendar(connection: GoogleCalendarConnection) -> dict:
    return _api(connection, "/users/me/calendarList/primary")


def list_calendars(connection: GoogleCalendarConnection) -> list[dict]:
    result = _api(connection, "/users/me/calendarList?minAccessRole=writer&maxResults=250")
    return result.get("items", [])


def save_connection(user_id: int, tenant_id: int, token_payload: dict) -> GoogleCalendarConnection:
    refresh_token = token_payload.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google did not return a refresh token; reconnect with consent")
    connection = GoogleCalendarConnection.query.filter_by(user_id=user_id, tenant_id=tenant_id).one_or_none()
    if connection is None:
        connection = GoogleCalendarConnection(user_id=user_id, tenant_id=tenant_id, refresh_token_encrypted=_encrypt(refresh_token))
        db.session.add(connection)
    else:
        connection.refresh_token_encrypted = _encrypt(refresh_token)
    connection.calendar_id = connection.calendar_id or "primary"
    db.session.flush()
    try:
        primary = get_primary_calendar(connection)
        connection.google_email = primary.get("id") or token_payload.get("id_token_email")
        connection.calendar_id = connection.calendar_id or primary.get("id") or "primary"
        connection.calendar_name = primary.get("summaryOverride") or primary.get("summary") or "היומן הראשי"
    except Exception:
        connection.google_email = token_payload.get("id_token_email") or connection.google_email
    db.session.commit()
    return connection


def get_connection(user_id: int, tenant_id: int) -> GoogleCalendarConnection | None:
    return GoogleCalendarConnection.query.filter_by(user_id=user_id, tenant_id=tenant_id).one_or_none()


def delete_connection(user_id: int, tenant_id: int) -> None:
    connection = get_connection(user_id, tenant_id)
    if connection:
        db.session.delete(connection)
        db.session.commit()


def _localize(value: datetime) -> datetime:
    tz_name = current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem")
    target = ZoneInfo(tz_name)
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(target)


def event_payload(order, *, frontend_url: str | None = None) -> dict:
    reminder_at = order.next_reminder_at
    if not reminder_at:
        raise ValueError("Order has no scheduled reminder")
    start = _localize(reminder_at)
    end = start + timedelta(minutes=30)
    url = (frontend_url or current_app.config.get("FRONTEND_PUBLIC_URL", "")).rstrip("/") + f"/dashboard/orders/{order.id}"
    description = (
        f"מעקב הזמנה {order.order_number}\n"
        f"ספק: {order.supplier_name}\n\n"
        "נוצר אוטומטית מ-SSOS.\n"
        + (f"פתיחת ההזמנה: {url}" if url else "")
    )
    return {
        "summary": f"מעקב הזמנה {order.order_number} – {order.supplier_name}",
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem")},
        "end": {"dateTime": end.isoformat(), "timeZone": current_app.config.get("GOOGLE_CALENDAR_TIMEZONE", "Asia/Jerusalem")},
        "visibility": "private",
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
    }


def sync_order_event(order, *, frontend_url: str | None = None) -> str | None:
    connection = get_connection(order.user_id, order.tenant_id)
    if not connection or not order.next_reminder_at:
        return None
    payload = event_payload(order, frontend_url=frontend_url)
    if order.google_calendar_event_id:
        try:
            _api(connection, f"/calendars/{urllib.parse.quote(connection.calendar_id, safe='')}/events/{urllib.parse.quote(order.google_calendar_event_id, safe='')}", method="PUT", payload=payload)
            return order.google_calendar_event_id
        except RuntimeError as exc:
            if "(404)" not in str(exc):
                raise
    result = _api(connection, f"/calendars/{urllib.parse.quote(connection.calendar_id, safe='')}/events", method="POST", payload=payload)
    event_id = result.get("id")
    order.google_calendar_event_id = event_id
    return event_id


def delete_order_event(order) -> None:
    connection = get_connection(order.user_id, order.tenant_id)
    event_id = order.google_calendar_event_id
    if not connection or not event_id:
        order.google_calendar_event_id = None
        return
    try:
        _api(connection, f"/calendars/{urllib.parse.quote(connection.calendar_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}", method="DELETE")
    except RuntimeError as exc:
        if "(404)" not in str(exc):
            raise
    order.google_calendar_event_id = None
