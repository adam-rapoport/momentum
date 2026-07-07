---
name: roadmap-update
description: Update or reprioritize the product roadmap — add an initiative, absorb a slip, or rebuild the Now/Next/Later view.
slash_command: roadmap-update
trigger_keywords: ["roadmap update", "update the roadmap", "reprioritize the roadmap", "reshuffle the roadmap"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Roadmap-Update Workflow

You are updating the product roadmap. The deliverable is a markdown
roadmap document the user can circulate — a Now/Next/Later view (or the
user's own column scheme) where every change from the previous version
is explicit and justified. A roadmap update that silently rewrites
history is worse than no update at all.

## Phase 1: Intake

FIRST, before asking anything:

1. Call `TimeCheck` — column boundaries and "this quarter" language
   depend on today's date.
2. Call `RecallMemory` once each for `type=product` (current roadmap
   state, active initiatives, carryover), `type=decision` (committed
   dates, deferrals, scope cuts — the constraints a roadmap change must
   respect), and `type=lessons` (patterns from retros that should shape
   sequencing). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Call `ListDocuments` and look for the current roadmap (title starts
   with "Roadmap"). If found, `ReadDocument` it — **the previous
   roadmap is your baseline**, and the new document must state deltas
   against it. If none exists, say so in one line and note you are
   building the first one.
4. Present what you found in 2-3 bullets ("Here's the roadmap state I
   have — correct anything wrong"), then ask ONLY what memory and the
   conversation haven't answered.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message covers everything, go straight
to Phase 2.

First message:
1. **What triggered this update?** A new initiative, a slipped
   dependency, a priority shift, or a periodic refresh. The trigger
   shapes the whole doc.
2. **What's the change?** What should move, be added, or be dropped —
   in their words.

Second message — one compact checklist:
3. **What gives?** If something is added or pulled forward, what moves
   down or out to make room? If they don't know, that becomes the
   central tradeoff of the doc, not a silent omission.
4. **Owners.** Who is accountable for anything newly in "Now" or
   "Next"? Unowned items stay in "Later".

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Roadmap: Now / Next / Later —
<month year>" and `content_markdown` structured as:

- `# <Title>`
- `## What Changed` — the headline: each moved/added/dropped item as
  "**<item>**: <was> → <now> — <why>", citing the trigger. This section
  is the reason the doc exists; write it first and best.
- `## Now` / `## Next` / `## Later` — tables with **Item | Owner |
  Notes**. Keep the user's own column names if they use different ones.
- `## Tradeoffs` — what was displaced to make room, or an explicit "no
  displacement: <why capacity allows this>". Never add work without
  naming its cost.
- `## Risks & Dependencies` — what could invalidate this version, and
  which items depend on others (or on external events).
- `## Decisions Needed` — anything the user must take to a stakeholder
  before this roadmap is real.
- `## Memory Updates` — propose `type=product` entries for the new
  roadmap state (and `type=decision` if a committed item moved). They
  are proposals until saved in Phase 3 — never mark one "Saved" in the
  doc.

### Depth guardrails

- **Every move cites its cause.** "Salesforce moved to Q3" is a fact;
  "Salesforce moved to Q3 — deferred on May 20 to protect the v2 beta"
  is a roadmap entry. Causes come from the user, memory, or a document
  — if unknown, write "cause unconfirmed" and list it in Decisions
  Needed.
- **Check committed items against `type=decision` memory before moving
  them.** Moving an item a logged decision committed to a date or
  quarter is a *decision change*, not a shuffle — flag it explicitly in
  What Changed and in Decisions Needed. Never present a change as
  continuity.
- **Deltas are explicit.** Anything different from the previous roadmap
  document appears in What Changed. If you couldn't find a previous
  roadmap, say so in the doc rather than implying continuity.
- **Owners come from a source or are "Owner TBD".** Never guess an
  owner from vibes; an unowned "Next" item gets flagged, not invented.
- **No new dates.** Quarters and sprint boundaries come from sources or
  the user. A hoped-for date is a "target (proposed)", never a bare
  date.
- **Keep it scannable.** A roadmap is a communication artifact: tables
  over prose, one line of Notes per item, details belong in linked
  initiative docs — not here.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "roadmap_update"`
- `document_id: <slug>`
- `summary_for_user: <one line: trigger, biggest move, and any decision
  change it implies>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the new roadmap state; `type=decision`
if a committed item moved): one short confirmation listing the entries,
then save what the user okays. Then the skill completes.
