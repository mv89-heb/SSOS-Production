from __future__ import annotations

import urllib.parse

from app.services import google_calendar_service as gcal


def get_event_html_link(connection, event_id: str | None) -> str | None:
    if not connection or not event_id:
        return None
    calendar_id = urllib.parse.quote(connection.calendar_id, safe="")
    encoded_event_id = urllib.parse.quote(event_id, safe="")
    try:
        result = gcal._api(
            connection,
            f"/calendars/{calendar_id}/events/{encoded_event_id}",
        )
        return result.get("htmlLink")
    except Exception:
        return None
