"""PM-specific tools: QueryTickets.

MVP note: QueryTickets returns mock data. A real Jira/Linear integration
is post-MVP — for now this proves out the pattern and gives the agent
something to reference when the user asks about tickets.
"""
from __future__ import annotations

from app.core.tools import Tool, register

# Tiny demo dataset so the model has something coherent to pattern-match on.
_MOCK_TICKETS = [
    {
        "id": "DXP-142",
        "title": "Onboarding funnel: gate the activation event on first successful action",
        "status": "in_progress",
        "assignee": "alex@local.dev",
        "project": "DXP",
        "priority": "P1",
    },
    {
        "id": "DXP-137",
        "title": "Instrument day-7 retention cohort view in Mixpanel",
        "status": "todo",
        "assignee": "jamie@local.dev",
        "project": "DXP",
        "priority": "P1",
    },
    {
        "id": "DXP-128",
        "title": "Kill the legacy signup A/B test (finished 2 weeks ago)",
        "status": "todo",
        "assignee": "alex@local.dev",
        "project": "DXP",
        "priority": "P2",
    },
    {
        "id": "DXP-115",
        "title": "Experiment doc template — align with new PRD structure",
        "status": "done",
        "assignee": "jamie@local.dev",
        "project": "DXP",
        "priority": "P2",
    },
    {
        "id": "INFRA-88",
        "title": "Redis connection pool tuning for session cancel path",
        "status": "in_progress",
        "assignee": "sarah@local.dev",
        "project": "INFRA",
        "priority": "P0",
    },
]


async def _query_tickets(input_data: dict) -> str:
    project = (input_data.get("project") or "").strip().upper()
    status = (input_data.get("status") or "").strip().lower()
    assignee = (input_data.get("assignee") or "").strip().lower()

    matches = _MOCK_TICKETS
    if project:
        matches = [t for t in matches if t["project"] == project]
    if status:
        matches = [t for t in matches if t["status"] == status]
    if assignee:
        matches = [t for t in matches if t["assignee"] == assignee]

    header = (
        "(MOCK DATA — real Jira integration is post-MVP. "
        "Tell the user these tickets are placeholders if they ask for source.)"
    )
    if not matches:
        return f"{header}\n\nNo tickets match the filters."

    lines = [header, "", f"Matched {len(matches)} ticket(s):", ""]
    for t in matches:
        lines.append(
            f"- [{t['id']}] ({t['priority']}, {t['status']}, {t['assignee']}) — {t['title']}"
        )
    return "\n".join(lines)


QueryTickets = register(
    Tool(
        name="QueryTickets",
        description=(
            "Look up Jira-style tickets by project, status, and/or assignee. "
            "IMPORTANT: This is currently a mock implementation returning "
            "fake demo data — when you use it, flag to the user that the "
            "results are placeholders until the real integration ships. "
            "Still useful for reasoning about workflow and what the final "
            "integration will look like."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project key (e.g., 'DXP', 'INFRA'). Case-insensitive.",
                },
                "status": {
                    "type": "string",
                    "description": "Status filter (e.g., 'todo', 'in_progress', 'done').",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assignee email to filter by.",
                },
            },
            "additionalProperties": False,
        },
        handler=_query_tickets,
        is_read_only=True,
        is_externally_visible=False,
        category="pm",
    )
)
