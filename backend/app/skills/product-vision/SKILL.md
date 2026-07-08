---
name: product-vision
description: Write a product vision narrative or Amazon-style PR-FAQ — a dated future press release, hard-question FAQ, and the bridge from today to there.
slash_command: product-vision
trigger_keywords: ["vision doc", "vision document", "draft a product vision", "write a product vision", "vision narrative", "prfaq", "pr faq", "pr-faq"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Product-Vision Workflow

You are writing a product vision, in one of two formats — intake
determines which:

- **PR-FAQ**: an Amazon-style future press release plus the FAQ that
  interrogates it.
- **Vision narrative**: a prose doc — the world today, the world
  we're building, and the bridge between them.

Both are deliberately aspirational documents, and that is exactly why
the line matters: everything about TODAY is grounded fact; everything
about the FUTURE is labeled vision. A vision doc that blurs which is
which becomes a fabrication generator for every doc written after it.

## Phase 1: Intake

FIRST, before asking anything (if the product/scope for the vision
wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — the vision's future dateline is computed from
   today, and labeled.
2. Call `RecallMemory` with the product as the query, once each for
   `type=product` (what's true today — the launch pad), `type=decision`
   (strategic bets already placed — the vision extends them or
   explicitly proposes reversing them), `type=stakeholder` (whose
   conviction the vision must win), and `type=lessons` (past vision
   exercises and their fate). If a typed pull returns nothing, try
   one broader `SearchMemories` query, then move on — do not stall.
3. Read the PRIMARY sources in full: the strategy memo (the vision
   must extend, not contradict, the chosen strategy) and the roadmap
   (what's already committed on the way there). Uploaded files live
   as reference memories; `ListDocuments` mostly shows generated
   deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the today-state
   and strategy I'll build the vision on — correct anything wrong"),
   then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the format (PR-FAQ or narrative), the horizon and dateline, the
today-facts you'll ground on (with sources), and the strategy bets
the vision extends — and end your turn so the user can steer before
you draft.

First message:
1. **Format and horizon.** PR-FAQ or narrative, and how far out
   (the dateline year)?
2. **What's it for?** An offsite, a funding ask, aligning a team —
   the audience sets the altitude.

Second message — one compact checklist:
3. **The core belief.** The one change in the customer's world this
   product should cause — in the user's words.
4. **Fixed points.** Anything the vision must include or must not
   touch (committed bets, sacred constraints).

## Phase 2: Drafting

### PR-FAQ format

Call `WriteDocument` with a `title` like "PR-FAQ: <product>
(<dateline year>)" and `content_markdown` structured as:

- `# <Title>`
- `## Press Release` — dateline "<City> — <future date>" computed
  from the horizon. Structure: headline (the customer's win, not
  the feature), one-paragraph what-launched, the problem it kills,
  how it works (customer's-eye view), one customer quote and one
  company quote, and how to get it. ~1 page. Written entirely in
  the future's present tense.
- `## FAQ` — the hard questions, honestly answered, split into:
  **External** (what customers/press would ask) and **Internal**
  (what leadership would ask: why us, why now, what it cannibalizes,
  what kills it, what it costs). 6-10 questions. The internal
  answers ground in today's sourced facts and name the gaps between
  today and the press release.
- `## Today vs the Vision` — table: **Claim in the PR | Status
  today | What closes the gap**. Every capability the press release
  asserts appears here with its honest today-status (sourced) —
  this table is the fabrication firewall.
- `## Open Questions` — what the sources couldn't settle.
- `## Memory Updates` — propose a `type=product` entry (the vision's
  core bet + horizon, IF approved as the working vision). Proposals
  until saved in Phase 3 — never mark one "Saved" in the doc.

### Narrative format

Same rules, structured as: `## The World Today` (sourced facts
only), `## The World We're Building` (the vision, labeled), `## Why
We Win` (tied to real capabilities and placed bets), `## The Bridge`
(today → vision in 2-4 stages; committed stages cite the roadmap,
uncommitted ones are labeled proposed), `## What We're NOT Saying`
(scope edges), `## Open Questions`, `## Memory Updates`.

### Depth guardrails

- **Two tenses, one line between them.** Facts about today (metrics,
  customers, capabilities) are verbatim from sources. Everything
  future-tense is vision by construction — and the doc says so once,
  clearly, at the top of the press release or vision section
  ("Aspirational — dateline <year>").
- **Vision quotes are fiction and look it.** The press release's
  customer/company quotes are illustrative by genre convention:
  attribute them to invented personas or role titles ("a mid-market
  ops lead"), NEVER to a real customer, account, or stakeholder from
  memory — putting future words in a real person's mouth is
  fabrication even inside a vision doc. Real people may appear only
  quoting things they actually said, from a source.
- **The future must be reachable from the present.** Every press-
  release claim lands in the Today-vs-Vision table with a sourced
  today-status. A claim with no plausible bridge either gets a
  bridge stage or gets cut — that's the FAQ's "what kills it"
  material, not fine print.
- **Extend the strategy or flag the departure.** Where the vision
  goes beyond the strategy memo's bets, label the extension; where
  it contradicts one, flag it as a proposed strategy change — never
  present a reversal as continuity.
- **No invented today-numbers to make the future look close.**
  Market sizes, adoption stats, and today-metrics appear only with
  sources; the vision's ambition needs no fabricated runway.
- **One follow-up per thin answer.** If the horizon or core belief
  is vague, ask at most ONE follow-up, then draft with what you
  have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "product_vision"`
- `document_id: <slug>`
- `summary_for_user: <one line: format, horizon, the headline bet>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the approved vision bet + horizon):
one short confirmation listing the entries, then save what the user
okays. Then the skill completes.
