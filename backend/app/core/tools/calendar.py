"""Google Calendar tools: ListCalendarEvents, FindAvailability,
CreateCalendarEvent.

Chunk C ships all three against the unified Google integration. Events
with attendees are created with invites suppressed — sending invites
requires the pause-and-review flow that lands in Chunk E.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.integrations.google_calendar import (
    CalendarError,
    CalendarNotConnected,
    create_event,
    find_availability,
    list_events,
)
from app.core.integrations.google_oauth import OAuthFlowError
from app.core.pending_actions import stage_action
from app.core.tools import Tool, get_context, register

logger = logging.getLogger(__name__)


def _normalize_email_list(value: Any, field: str) -> list[str] | str:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, list):
        return [str(p).strip() for p in value if str(p).strip()]
    return f"Error: '{field}' must be a list of email addresses."


def _format_error(e: Exception, action: str) -> str:
    if isinstance(e, CalendarNotConnected):
        return f"Error: {e}"
    if isinstance(e, OAuthFlowError):
        return f"Error: Google authentication expired — reconnect in Settings. ({e})"
    if isinstance(e, CalendarError):
        return f"Error: Calendar {action} failed: {e}"
    if isinstance(e, ValueError):
        return f"Error: {e}"
    return f"Error: Calendar {action} failed: {e}"


async def _list_calendar_events(input_data: dict) -> str:
    time_min = (input_data.get("time_min") or "").strip()
    time_max = (input_data.get("time_max") or "").strip()
    if not time_min or not time_max:
        return "Error: 'time_min' and 'time_max' are required (ISO-8601 with offset)."
    calendar_id = (input_data.get("calendar_id") or "primary").strip() or "primary"
    max_results_raw = input_data.get("max_results", 20)
    try:
        max_results = int(max_results_raw)
    except (TypeError, ValueError):
        return "Error: 'max_results' must be an integer (1-50)."

    ctx = get_context()
    try:
        events = await list_events(
            ctx.db,
            ctx.user_id,
            time_min=time_min,
            time_max=time_max,
            calendar_id=calendar_id,
            max_results=max_results,
        )
    except (CalendarNotConnected, CalendarError, OAuthFlowError, ValueError) as e:
        return _format_error(e, "list")

    if not events:
        return f"No events between {time_min} and {time_max}."

    lines = [f"{len(events)} event(s):", ""]
    for e in events:
        attendee_line = ""
        if e["attendees"]:
            emails = [a["email"] for a in e["attendees"] if a["email"]]
            attendee_line = f"\n   attendees: {', '.join(emails)}"
        loc_line = f"\n   location: {e['location']}" if e["location"] else ""
        lines.append(
            f"- **{e['summary']}**\n"
            f"   {e['start']} → {e['end']}"
            f"{loc_line}{attendee_line}\n"
            f"   id: `{e['id']}`  ·  [open]({e['html_link']})"
        )
    return "\n".join(lines)


async def _find_availability(input_data: dict) -> str:
    time_min = (input_data.get("time_min") or "").strip()
    time_max = (input_data.get("time_max") or "").strip()
    if not time_min or not time_max:
        return "Error: 'time_min' and 'time_max' are required (ISO-8601 with offset)."

    duration_raw = input_data.get("duration_minutes")
    if duration_raw is None:
        return "Error: 'duration_minutes' is required."
    try:
        duration = int(duration_raw)
    except (TypeError, ValueError):
        return "Error: 'duration_minutes' must be a positive integer."

    calendar_ids_raw = input_data.get("calendar_ids")
    calendar_ids: list[str] | None
    if calendar_ids_raw is None:
        calendar_ids = None
    elif isinstance(calendar_ids_raw, list):
        calendar_ids = [str(c).strip() for c in calendar_ids_raw if str(c).strip()]
    else:
        calendar_ids = [str(calendar_ids_raw).strip()]

    ctx = get_context()
    try:
        slots = await find_availability(
            ctx.db,
            ctx.user_id,
            time_min=time_min,
            time_max=time_max,
            duration_minutes=duration,
            calendar_ids=calendar_ids,
        )
    except (CalendarNotConnected, CalendarError, OAuthFlowError, ValueError) as e:
        return _format_error(e, "availability")

    if not slots:
        return (
            f"No free slots of {duration} minutes between {time_min} and {time_max} "
            f"across {', '.join(calendar_ids) if calendar_ids else 'primary'}."
        )

    lines = [f"{len(slots)} free slot(s) of at least {duration} minutes:", ""]
    for s in slots:
        lines.append(f"- {s['start']} → {s['end']}  ({s['duration_minutes']} min)")
    return "\n".join(lines)


async def _create_calendar_event(input_data: dict) -> str:
    summary = (input_data.get("summary") or "").strip()
    start_iso = (input_data.get("start_iso") or "").strip()
    end_iso = (input_data.get("end_iso") or "").strip()
    if not summary:
        return "Error: 'summary' is required."
    if not start_iso or not end_iso:
        return "Error: 'start_iso' and 'end_iso' are required (ISO-8601 with offset)."

    description = input_data.get("description") or ""
    location = (input_data.get("location") or "").strip()
    calendar_id = (input_data.get("calendar_id") or "primary").strip() or "primary"

    attendees_parsed = _normalize_email_list(input_data.get("attendees"), "attendees")
    if isinstance(attendees_parsed, str):
        return attendees_parsed

    ctx = get_context()

    # Solo block (no attendees) → no external side effect, create directly.
    # Event with attendees → stage for approval. We don't even create the
    # event yet so a discarded /revise leaves nothing on the calendar.
    if not attendees_parsed:
        try:
            result = await create_event(
                ctx.db,
                ctx.user_id,
                summary=summary,
                start_iso=start_iso,
                end_iso=end_iso,
                description=description,
                location=location,
                attendees=None,
                calendar_id=calendar_id,
                send_updates="none",
            )
        except (CalendarNotConnected, CalendarError, OAuthFlowError, ValueError) as e:
            return _format_error(e, "event create")
        return (
            f"Event created: '{result['summary']}' ({result['start']} → {result['end']})\n"
            f"Calendar URL: {result['html_link']}\n"
            f"_event_id: `{result['id']}`_"
        )

    # Has attendees → stage. Approval will run create_event with sendUpdates='all'.
    try:
        await stage_action(
            ctx.db,
            ctx.session_id,
            kind="create_event",
            tool_name="CreateCalendarEvent",
            params={
                "summary": summary,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "description": description,
                "location": location,
                "attendees": attendees_parsed,
                "calendar_id": calendar_id,
            },
            preview={
                "summary": summary,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "location": location,
                "attendees": attendees_parsed,
                "description": description,
            },
        )
    except ValueError as e:
        return f"Error: {e}"

    return (
        f"[Pending approval] Event staged: '{summary}' ({start_iso} → {end_iso}) "
        f"with {len(attendees_parsed)} attendee(s). SESSION PAUSING NOW. "
        f"Stop your turn here — emit no more text and call no more tools. "
        f"The user will click Approve, Make changes, or Cancel in the UI; "
        f"the next turn will start with a system note telling you the "
        f"final outcome. Calling CreateCalendarEvent again in this turn "
        f"would create a duplicate event."
    )


ListCalendarEvents = register(
    Tool(
        name="ListCalendarEvents",
        description=(
            "List events on the user's Google Calendar between two times. "
            "Expands recurring events into individual instances. Both "
            "'time_min' and 'time_max' must be ISO-8601 with a timezone "
            "offset (e.g. '2026-04-25T09:00:00-07:00'). Use TimeCheck first "
            "if you need the current time to build the window."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "time_min": {
                    "type": "string",
                    "description": "Start of window (ISO-8601 with offset).",
                },
                "time_max": {
                    "type": "string",
                    "description": "End of window (ISO-8601 with offset).",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Which calendar to query. Default 'primary'.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Max events to return. Default 20, max 50.",
                },
            },
            "required": ["time_min", "time_max"],
            "additionalProperties": False,
        },
        handler=_list_calendar_events,
        is_read_only=True,
        is_externally_visible=False,
        category="calendar",
    )
)


FindAvailability = register(
    Tool(
        name="FindAvailability",
        description=(
            "Find free time slots of at least 'duration_minutes' within a "
            "window on the user's calendar(s). Use when the user asks for "
            "availability ('find a 30-min slot this afternoon', 'when am I "
            "free Friday'). All times must be ISO-8601 with offset. For "
            "multi-person availability, include their email in "
            "'calendar_ids' (only works if the user has Calendar view access)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "time_min": {
                    "type": "string",
                    "description": "Start of window (ISO-8601 with offset).",
                },
                "time_max": {
                    "type": "string",
                    "description": "End of window (ISO-8601 with offset).",
                },
                "duration_minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Minimum slot duration in minutes.",
                },
                "calendar_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Calendar IDs to scan. Default ['primary']. Add colleagues' emails to find joint availability.",
                },
            },
            "required": ["time_min", "time_max", "duration_minutes"],
            "additionalProperties": False,
        },
        handler=_find_availability,
        is_read_only=True,
        is_externally_visible=False,
        category="calendar",
    )
)


CreateCalendarEvent = register(
    Tool(
        name="CreateCalendarEvent",
        description=(
            "Create an event on the user's Google Calendar. Solo blocks (no "
            "attendees) are created immediately. Events with attendees are "
            "STAGED for approval — the user sees a preview and clicks "
            "Approve before invites are sent. If the user revises, just "
            "call CreateCalendarEvent again with the updated parameters. "
            "All times must be ISO-8601 with an explicit timezone offset."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Event title.",
                },
                "start_iso": {
                    "type": "string",
                    "description": "Start time (ISO-8601 with offset, e.g. '2026-04-25T14:00:00-07:00').",
                },
                "end_iso": {
                    "type": "string",
                    "description": "End time (ISO-8601 with offset). Must be after start.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional event description.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional location (venue, URL).",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional attendee email addresses. Adding attendees triggers the approval flow before invites are sent.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Target calendar (default 'primary').",
                },
            },
            "required": ["summary", "start_iso", "end_iso"],
            "additionalProperties": False,
        },
        handler=_create_calendar_event,
        is_read_only=False,
        is_externally_visible=True,
        category="calendar",
    )
)
