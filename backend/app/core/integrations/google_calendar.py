"""Google Calendar adapter — thin wrapper over Calendar v3 REST API.

Same shape as `gmail.py` / `google_docs.py`: one `_get_integration` +
`_build_calendar` pair that reuses the unified Google OAuth credentials,
then async helpers the tools call.

Design choices for MVP simplicity:
- All input times must be ISO-8601 with an explicit timezone offset
  (e.g. `2026-04-25T14:00:00-07:00`). Naive datetimes get rejected —
  we refuse to guess the user's intended zone.
- Availability: use freebusy.query to get busy blocks across the
  requested calendars, then subtract from the user-supplied window.
  No fancy working-hours / timezone math — the caller is expected to
  pass the window they actually want scanned.
- Event creation: always creates with `sendUpdates='none'` in this
  chunk so no invite emails go out. Chunk E will generalize the
  pause-and-review flow and then switch to `sendUpdates='all'` after
  the user approves the preview.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.integrations.google_oauth import (
    OAuthFlowError,
    PROVIDER,
    SCOPES,
    get_valid_access_token,
)
from app.models import Integration

logger = logging.getLogger(__name__)

DEFAULT_CALENDAR_ID = "primary"
MAX_EVENTS_PER_LIST = 50
READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"


class CalendarNotConnected(RuntimeError):
    pass


class CalendarError(RuntimeError):
    """Any Calendar API failure the user can act on."""


class CalendarApiNotEnabled(CalendarError):
    """Admin needs to enable Calendar API in Google Cloud Console."""


def _wrap_http_error(e: HttpError, action: str) -> CalendarError:
    status = getattr(getattr(e, "resp", None), "status", None)
    detail = ""
    try:
        details = getattr(e, "error_details", None) or []
        if details and isinstance(details, list):
            first = details[0]
            if isinstance(first, dict):
                reason = first.get("reason", "")
                detail = first.get("message", "") or ""
                if reason == "accessNotConfigured":
                    return CalendarApiNotEnabled(
                        "Calendar API is not enabled for this Google Cloud "
                        "project. Open https://console.developers.google.com"
                        "/apis/api/calendar-json.googleapis.com/overview and "
                        "click Enable, then wait ~30 seconds and retry."
                    )
    except Exception:  # noqa: BLE001
        pass
    if status == 403:
        return CalendarError(
            f"Calendar {action} denied (403). Scope or project config issue. {detail}".strip()
        )
    if status == 401:
        return CalendarError(
            f"Calendar {action} unauthorized (401). Reconnect Google in Settings."
        )
    if status == 404:
        return CalendarError(f"Calendar {action} target not found (404). {detail}".strip())
    return CalendarError(f"Calendar {action} failed ({status}). {detail}".strip())


async def _get_integration(
    db: AsyncSession, user_id, *, require_scope: str = READONLY_SCOPE
) -> Integration:
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    if integration is None or integration.status != "connected":
        raise CalendarNotConnected(
            "Google is not connected. Visit Settings to connect."
        )
    granted = set(integration.scopes or [])
    if require_scope not in granted:
        raise CalendarNotConnected(
            "Calendar permission not granted. Visit Settings and click "
            "Reconnect to grant access to Calendar."
        )
    return integration


async def _build_calendar(db: AsyncSession, integration: Integration):
    access_token = await get_valid_access_token(db, integration)
    creds = GoogleCredentials(token=access_token, scopes=SCOPES)
    return await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )


# ---------- Time parsing ----------


def _parse_aware_iso(value: str, field: str) -> datetime:
    """Parse an ISO-8601 string; require an explicit timezone offset.
    We refuse naive datetimes to avoid guessing the user's intended zone."""
    try:
        # `fromisoformat` accepts offsets like `-07:00` and `+00:00` from 3.11+
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise ValueError(
            f"'{field}' must be ISO-8601 with a timezone offset "
            f"(e.g. '2026-04-25T14:00:00-07:00'). Got: {value!r}"
        ) from e
    if dt.tzinfo is None:
        raise ValueError(
            f"'{field}' is missing a timezone offset. Pass ISO-8601 with "
            f"an explicit offset (e.g. '2026-04-25T14:00:00-07:00'), not "
            f"a naive datetime. Got: {value!r}"
        )
    return dt


def _to_rfc3339(dt: datetime) -> str:
    """Google Calendar wants RFC3339 — which is just ISO-8601 with a tz."""
    return dt.isoformat()


# ---------- Public helpers ----------


async def list_events(
    db: AsyncSession,
    user_id,
    *,
    time_min: str,
    time_max: str,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Return events in [time_min, time_max) on `calendar_id`, ordered by
    start time. Expands recurring events into individual instances."""
    integration = await _get_integration(db, user_id)
    calendar = await _build_calendar(db, integration)

    _parse_aware_iso(time_min, "time_min")
    _parse_aware_iso(time_max, "time_max")
    max_results = max(1, min(max_results, MAX_EVENTS_PER_LIST))

    def _sync_list() -> list[dict[str, Any]]:
        resp = (
            calendar.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )
        out: list[dict[str, Any]] = []
        for evt in resp.get("items", []):
            start = evt.get("start") or {}
            end = evt.get("end") or {}
            out.append(
                {
                    "id": evt.get("id", ""),
                    "summary": evt.get("summary", "(untitled)"),
                    "description": evt.get("description", ""),
                    "location": evt.get("location", ""),
                    "start": start.get("dateTime") or start.get("date") or "",
                    "end": end.get("dateTime") or end.get("date") or "",
                    "all_day": "date" in start and "dateTime" not in start,
                    "attendees": [
                        {
                            "email": a.get("email", ""),
                            "response": a.get("responseStatus", ""),
                            "self": bool(a.get("self")),
                        }
                        for a in (evt.get("attendees") or [])
                    ],
                    "organizer_email": (evt.get("organizer") or {}).get("email", ""),
                    "status": evt.get("status", ""),
                    "html_link": evt.get("htmlLink", ""),
                }
            )
        return out

    try:
        return await asyncio.to_thread(_sync_list)
    except HttpError as e:
        raise _wrap_http_error(e, "list") from e
    except OAuthFlowError:
        raise


async def find_availability(
    db: AsyncSession,
    user_id,
    *,
    time_min: str,
    time_max: str,
    duration_minutes: int,
    calendar_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    """Return free slots of at least `duration_minutes` within
    [time_min, time_max] across the given calendars (default: primary).

    Algorithm: freebusy.query returns busy blocks; we subtract those
    from the outer window, merge overlapping busy blocks across
    calendars, then emit any remaining gap that's long enough."""
    integration = await _get_integration(db, user_id)
    calendar = await _build_calendar(db, integration)

    start_dt = _parse_aware_iso(time_min, "time_min")
    end_dt = _parse_aware_iso(time_max, "time_max")
    if end_dt <= start_dt:
        raise ValueError("'time_max' must be after 'time_min'.")
    if duration_minutes <= 0:
        raise ValueError("'duration_minutes' must be a positive integer.")
    duration = timedelta(minutes=duration_minutes)

    if not calendar_ids:
        calendar_ids = [DEFAULT_CALENDAR_ID]

    def _sync_query() -> list[tuple[datetime, datetime]]:
        resp = (
            calendar.freebusy()
            .query(
                body={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "items": [{"id": cid} for cid in calendar_ids],
                }
            )
            .execute()
        )
        busy: list[tuple[datetime, datetime]] = []
        for cid, info in (resp.get("calendars") or {}).items():
            for block in info.get("busy") or []:
                try:
                    bstart = _parse_aware_iso(block["start"], "busy.start")
                    bend = _parse_aware_iso(block["end"], "busy.end")
                except (KeyError, ValueError):
                    logger.warning("skipping malformed busy block from %s: %s", cid, block)
                    continue
                busy.append((bstart, bend))
        return busy

    try:
        busy = await asyncio.to_thread(_sync_query)
    except HttpError as e:
        raise _wrap_http_error(e, "freebusy") from e
    except OAuthFlowError:
        raise

    merged = _merge_intervals(busy)
    gaps = _subtract_intervals(start_dt, end_dt, merged)
    slots: list[dict[str, str]] = []
    for gstart, gend in gaps:
        if gend - gstart >= duration:
            slots.append(
                {
                    "start": _to_rfc3339(gstart),
                    "end": _to_rfc3339(gend),
                    "duration_minutes": int((gend - gstart).total_seconds() // 60),
                }
            )
    return slots


def _merge_intervals(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda iv: iv[0])
    merged: list[tuple[datetime, datetime]] = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _subtract_intervals(
    window_start: datetime,
    window_end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Return the gaps within [window_start, window_end] not covered by any
    interval in `busy`. Assumes `busy` is already merged + sorted."""
    gaps: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for bstart, bend in busy:
        if bend <= cursor:
            continue
        if bstart >= window_end:
            break
        if bstart > cursor:
            gaps.append((cursor, min(bstart, window_end)))
        cursor = max(cursor, bend)
        if cursor >= window_end:
            break
    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps


async def create_event(
    db: AsyncSession,
    user_id,
    *,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    send_updates: str = "none",
) -> dict[str, Any]:
    """Create a calendar event.

    `send_updates` controls Google's invite-email behavior:
      - "none" (default): no notification emails. Used by the tool layer
        when staging events for approval — keeps the system safe even
        if the staged event is created before the user clicks Approve.
      - "all": notify every attendee. Used by `pending_actions` after
        the user approves the preview in the UI.
      - "externalOnly": notify non-Workspace attendees only.
    """
    integration = await _get_integration(db, user_id, require_scope=EVENTS_SCOPE)
    calendar = await _build_calendar(db, integration)

    start_dt = _parse_aware_iso(start_iso, "start_iso")
    end_dt = _parse_aware_iso(end_iso, "end_iso")
    if end_dt <= start_dt:
        raise ValueError("'end_iso' must be after 'start_iso'.")
    if not summary.strip():
        raise ValueError("'summary' is required.")
    if send_updates not in ("none", "all", "externalOnly"):
        raise ValueError(
            f"send_updates must be one of 'none', 'all', 'externalOnly'; got {send_updates!r}"
        )

    # Preserve the user's declared timezone offset so Calendar renders
    # the event at the clock time they intended, not UTC.
    body: dict[str, Any] = {
        "summary": summary,
        "start": {
            "dateTime": _to_rfc3339(start_dt),
            "timeZone": _tz_name(start_dt),
        },
        "end": {
            "dateTime": _to_rfc3339(end_dt),
            "timeZone": _tz_name(end_dt),
        },
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    def _sync_create() -> dict[str, Any]:
        return (
            calendar.events()
            .insert(
                calendarId=calendar_id,
                body=body,
                sendUpdates=send_updates,
            )
            .execute()
        )

    try:
        evt = await asyncio.to_thread(_sync_create)
    except HttpError as e:
        raise _wrap_http_error(e, "event create") from e
    except OAuthFlowError:
        raise

    return {
        "id": evt.get("id", ""),
        "summary": evt.get("summary", summary),
        "start": evt.get("start", {}).get("dateTime", start_iso),
        "end": evt.get("end", {}).get("dateTime", end_iso),
        "html_link": evt.get("htmlLink", ""),
        "attendees_count": len(attendees or []),
        "invites_sent": send_updates != "none",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _tz_name(dt: datetime) -> str:
    """Best-effort IANA-ish timezone name. If we can't resolve one, emit
    the offset — Calendar accepts either."""
    if dt.tzinfo is None:
        return "UTC"
    name = dt.tzname() or ""
    # Prefer a proper IANA name if zoneinfo gave us one ("America/Los_Angeles").
    if "/" in name:
        return name
    # Fallback to the numeric offset ("+00:00" -> "UTC", "-0700" -> "-0700").
    offset = dt.utcoffset()
    if offset is None or offset == timedelta(0):
        return "UTC"
    return name or "UTC"


async def is_connected(db: AsyncSession, user_id) -> bool:
    try:
        await _get_integration(db, user_id)
        return True
    except CalendarNotConnected:
        return False
