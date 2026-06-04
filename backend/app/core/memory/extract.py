"""Turn an uploaded reference document into structured memories.

When a user uploads a doc during onboarding, the raw text is saved as a single
`reference` memory (the source of truth — see app.api.onboarding). This module
additionally asks the user's *heavy* model to read that text and pull out the
durable facts a PM would want the agent to remember (stakeholders, decisions,
product details, team norms, lessons), saving each through the same
`save_memory` store the chat agent's SaveMemory tool uses.

It is deliberately best-effort: the caller wraps it in try/except so a model
hiccup never blocks the upload — the reference memory is already safe.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import credentials, llm
from app.core.groq_client import StreamChunk, StreamResult
from app.core.memory.store import ALLOWED_TYPES, save_memory
from app.core.model_router import select_model
from app.models import MemoryRecord, Project, User

logger = logging.getLogger(__name__)

# Cap how much of the doc we hand the model — enough for rich context without
# blowing the heavy model's context window on a very long upload.
MAX_DOC_CHARS = 12_000
# Safety bound on how many memories one document can spawn.
MAX_MEMORIES = 12

# Types worth auto-extracting. `reference` is excluded: the whole document is
# already saved as a reference memory, so derived items should be the *facts*.
_EXTRACTABLE_TYPES = sorted(ALLOWED_TYPES - {"reference"})

_SYSTEM_PROMPT = (
    "You help a product manager build durable memory from a reference "
    "document. Read the document and extract the specific, durable facts worth "
    "remembering across future conversations — stakeholders and their "
    "preferences, decisions and their rationale, product/company details, team "
    "norms, and lessons learned.\n\n"
    "Return ONLY a JSON array (no prose, no code fences). Each element is an "
    'object: {"type": <one of '
    + ", ".join(_EXTRACTABLE_TYPES)
    + '>, "title": <short label>, "summary": <one sentence>, "content": '
    "<the detail, in markdown>}.\n\n"
    "Rules: only include genuinely useful, durable facts (skip filler and "
    "transient details); keep titles short and specific; if the document has "
    "nothing worth remembering, return []."
)


def _parse_memory_json(text: str) -> list[dict]:
    """Pull a JSON array of memory objects out of the model's reply.

    Tolerant of code fences and surrounding prose (e.g. a heavy model's
    chain-of-thought) by slicing from the first '[' to the last ']'. Returns
    [] on any parse failure — extraction is best-effort.
    """
    if not text:
        return []
    # Strip ```json ... ``` fences if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("[")
    end = candidate.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(candidate[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


async def _run_heavy(
    db: AsyncSession, user: User, doc_title: str, doc_text: str
) -> str:
    """Resolve the user's heavy model + key and run a single completion."""
    configured = await credentials.configured_llm_providers(db, user.id)
    model = select_model(
        "",
        None,
        user_preferences=user.preferences,
        configured_providers=configured,
        force_heavy=True,
    )
    cred_provider = credentials.llm_provider_for_model(model)
    api_key = await credentials.resolve_api_key(db, user.id, cred_provider)
    if api_key is None:
        # No usable key for the heavy provider — skip rather than crash.
        logger.info("doc extraction skipped: no key for %s", cred_provider)
        return ""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Document title: {doc_title}\n\n---\n{doc_text[:MAX_DOC_CHARS]}",
        },
    ]
    chunks: list[str] = []
    final_text = ""
    async for event in llm.stream_message(messages, model=model, api_key=api_key):
        if isinstance(event, StreamResult):
            final_text = event.text
        elif isinstance(event, StreamChunk):
            chunks.append(event.text)
    return final_text or "".join(chunks)


async def extract_memories_from_document(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    doc_title: str,
    doc_text: str,
) -> list[MemoryRecord]:
    """Read `doc_text` with the heavy model and persist the facts it finds as
    memories. Returns the saved records (may be empty). Does NOT commit — the
    caller owns the transaction."""
    reply = await _run_heavy(db, user, doc_title, doc_text)
    items = _parse_memory_json(reply)

    saved: list[MemoryRecord] = []
    for item in items[:MAX_MEMORIES]:
        if not isinstance(item, dict):
            continue
        mem_type = item.get("type")
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if mem_type not in _EXTRACTABLE_TYPES or not title or not content:
            continue
        record = await save_memory(
            db=db,
            project=project,
            mem_type=mem_type,
            title=title,
            content=content,
            summary=(item.get("summary") or "").strip() or None,
            tags=["onboarding", "from-document"],
        )
        saved.append(record)

    logger.info(
        "doc extraction: %d memories from %r (%d chars)",
        len(saved),
        doc_title,
        len(doc_text),
    )
    return saved
