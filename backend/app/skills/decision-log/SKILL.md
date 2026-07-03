---
name: decision-log
description: Capture a product or architectural decision in a structured ADR-style log entry — context, options, decision, consequences.
slash_command: decision-log
trigger_keywords: ["decision log", "log a decision", "adr", "architecture decision record", "decision record"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory"]
phases: ["intake", "drafting", "review"]
---

# Decision-Log Workflow

You are capturing a decision (product, architectural, or process) so
the user — or their future team — can revisit *why* a choice was made
months later. Output is a single markdown doc per decision.

Follow the phases in order. Do NOT call `WriteDocument` during
intake; do not draft until Phase 2.

## Phase 1: Intake

PMs often log decisions after the fact in one brain-dump. If the
opening message already covers most of the seven items below, do NOT
run the question list — reflect back your reading in ONE message and
ask for at most the two most important gaps. If the user signals
speed ("just log it"), draft immediately: mark anything missing as
`TBD` and list each gap under Open Questions / Follow-ups.

As soon as you know the topic (from the opening message or question
1), call `RecallMemory` with `type="decision"` and `query=<2-3
keywords from the decision>`, then again with `type="product"`. If
the decision is technical, also `type="lessons"`. Use what comes back
to pre-fill questions 2–6 — confirm instead of asking — and to check
for a prior decision this one may supersede.

If recall surfaces a prior decision this one replaces or amends,
confirm with the user: "Does this supersede <prior title>?" If yes:
(a) add a `**Supersedes:** <prior decision title>` line under Status
in the new doc and list the old doc under References; (b) after
approval, offer to update the old decision doc via `EditDocument`,
changing its Status line to `Superseded — see <new title>`.

Otherwise, ask one at a time, skipping anything already supplied:

1. **The decision.** State it as a single sentence, in the form "We
   are going to X (rather than Y or Z)." If the user phrases it
   open-endedly, push gently for the actual choice.
2. **Context.** What forced this decision? What changed, what's the
   constraint, what's the deadline? Who asked or who's affected?
3. **Who decided.** Whose call was/is this — the user alone, or
   together with others? This fills the Decision-maker(s) line; never
   guess or fabricate a name. When the user says "I"/"me", resolve
   their actual name (and title if known) from the `User:` line in
   your context or memory (`RecallMemory` with `type="team"`, or
   `SearchMemories` by name) — never leave a generic role name when
   the real name is one lookup away.
4. **Options considered.** What did the user weigh? At minimum the
   chosen option and one alternative. Three or four is better — but
   don't fabricate; only what the user actually considered.
5. **Why this option won.** The deciding factor or factors. Specific.
6. **Consequences.** What does this make easier? Harder? What gets
   locked in? Anything they're explicitly accepting?
7. **Status.** Proposed (still being decided), Accepted (decided,
   not yet implemented), Implemented (done), or Superseded (replaced
   by a later decision)?

## Phase 2: Drafting

Use ADR-style structure. Call `WriteDocument` with `title` like
"Decision: <one-sentence decision>" and `content_markdown`:

- `# Decision: <one-sentence decision>`
- `**Status:** <Proposed | Accepted | Implemented | Superseded>`
- `**Supersedes:** <prior decision title>` — only when this replaces
  an earlier logged decision (see Phase 1)
- `**Date:** <YYYY-MM-DD>`
- `**Decision-maker(s):** <who>`
- `## Context` — 2-4 paragraphs. What's going on, what forced this,
  what constraints apply. The reader 6 months from now needs this to
  re-feel the situation
- `## Options Considered` — for each:
  - `### Option <N>: <name>`
  - One paragraph describing the option
  - `**Pros:**` — bullets
  - `**Cons:**` — bullets
- `## Decision` — 1-2 paragraphs. The chosen option AND the deciding
  factor. Not "we chose X" — "we chose X because <specific reason
  tied to context>"
- `## Consequences` — bulleted list. What this makes easier, harder,
  locked-in, or accepts as a tradeoff. Be honest about the downsides
- `## Open Questions / Follow-ups` — what we still don't know, or
  what needs to happen next
- `## References` — prior decision docs by title/slug, memories by
  title, and any external URLs the user provided. Local docs and
  memories have no URLs — cite them by name; never invent a link

### Depth guardrails

A decision log is only useful if it captures *why* a future reader
couldn't reconstruct from code or chat history. Hold yourself to:

- **Context names the forcing function.** "We needed to pick a
  database" is filler; "Existing Postgres instance hit IOPS limit
  during last week's spike, and the SRE team requires a decision by
  Friday so capex can be requested in this quarter" is the actual
  context.
- **At least 2 options, with real cons on the chosen one.** If the
  chosen option has no cons listed, you weren't honest with yourself
  about the tradeoff. Force at least one con per option.
- **The Decision section names the deciding factor.** Not "X had more
  pros" — "X let us preserve the existing query layer, which is the
  hard part to migrate; Y would have required rewriting that layer."
- **Consequences include downsides.** "We're now locked into vendor X
  for 12 months" or "Our infra cost goes up ~$2k/mo" belong here.
  Future-you needs to see what you traded.
- **Don't fabricate options.** If only two were seriously considered,
  list two. Adding a strawman third makes the doc less trustworthy.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "decision_log"`
- `document_id: <the slug returned by WriteDocument>`
- `summary_for_user: <one line: the decision + status>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.

On approval, before completing, call `SaveMemory` with
`type: "decision"`, `title` = the one-sentence decision, `summary` =
decision + status in under 120 chars, and `content` covering: what
was decided, the date, who decided, the deciding factor, and what was
traded off — plus the line "Full log: <document slug>". This step is
mandatory: documents are not searched by `RecallMemory`, so without
this memory the decision is invisible to future sessions. Then do
the superseded-doc status flip if one was agreed in Phase 1.
