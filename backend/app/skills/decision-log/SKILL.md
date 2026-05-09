---
name: decision-log
description: Capture a product or architectural decision in a structured ADR-style log entry — context, options, decision, consequences.
slash_command: decision-log
trigger_keywords: ["decision log", "log a decision", "record a decision", "adr", "architecture decision record", "decision record"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Decision-Log Workflow

You are capturing a decision (product, architectural, or process) so
the user — or their future team — can revisit *why* a choice was made
months later. Output is a single markdown doc per decision.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

1. **The decision.** State it as a single sentence, in the form "We
   are going to X (rather than Y or Z)." If the user phrases it
   open-endedly, push gently for the actual choice.
2. **Context.** What forced this decision? What changed, what's the
   constraint, what's the deadline? Who asked or who's affected?
3. **Options considered.** What did the user weigh? At minimum the
   chosen option and one alternative. Three or four is better — but
   don't fabricate; only what the user actually considered.
4. **Why this option won.** The deciding factor or factors. Specific.
5. **Consequences.** What does this make easier? Harder? What gets
   locked in? Anything they're explicitly accepting?
6. **Status.** Proposed (still being decided), Accepted (decided,
   not yet implemented), Implemented (done), or Superseded (replaced
   by a later decision)?

Pull `type=decision` (related past decisions — this one might supersede
or build on something) and `type=product` (the area being decided in).
If the decision is technical, also pull `type=lessons`.

## Phase 2: Drafting

Use ADR-style structure. Call `WriteDocument` with `title` like
"Decision: <one-sentence decision>" and `content_markdown`:

- `# Decision: <one-sentence decision>`
- `**Status:** <Proposed | Accepted | Implemented | Superseded>`
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
- `## References` — links to relevant memories, prior decisions, docs

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
- `document_id: <slug>`
- `summary_for_user: <one line: the decision + status>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
