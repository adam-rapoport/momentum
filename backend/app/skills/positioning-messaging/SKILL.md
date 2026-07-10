---
name: positioning-messaging
description: Write a positioning statement and messaging hierarchy — audience, category, differentiators, and message pillars with sourced proof points.
slash_command: positioning-messaging
trigger_keywords: ["positioning statement", "messaging hierarchy", "messaging framework", "positioning and messaging", "position the product"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Positioning-Messaging Workflow

You are writing positioning and messaging. The deliverable is a
markdown doc marketing and sales can build on: a positioning
statement whose every slot is a deliberate choice, and a messaging
hierarchy whose pillars stand on proof points that actually exist.
Positioning fails two ways — by being generic (true of every
competitor) or by being aspirational (not yet true of you). This
workflow guards both edges.

## Phase 1: Intake

FIRST, before asking anything (if the product/feature being
positioned wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — competitive claims and launch tie-ins age
   fast; date the doc.
2. Call `RecallMemory` with the product as the query, once each for
   `type=product` (real capabilities, metrics, and customer evidence
   — the proof-point pool), `type=decision` (segment or strategy
   choices positioning must serve), `type=stakeholder` (customers
   whose evidence or logos might be cited — and any sensitivities),
   and `type=lessons` (past messaging that landed or flopped). If a
   typed pull returns nothing, try one broader `SearchMemories`
   query, then move on — do not stall.
3. Read the PRIMARY sources in full: the competitive/landscape doc
   (who else claims what — your differentiator must survive it) and
   the strategy memo (which segment you're choosing to win).
   Uploaded files live as reference memories; `ListDocuments` mostly
   shows generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the positioning
   raw material I have — correct anything wrong"), then ask ONLY
   what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the target segment (with its source), the competitive alternative
you'll position against, and the proof points you found for each
candidate differentiator — and end your turn so the user can steer
before you draft.

First message:
1. **Who must this land with?** The segment and buyer/user, and the
   moment it's used (website, sales deck, launch).
2. **What's the real alternative?** What the target uses today —
   a named competitor, spreadsheets, doing nothing.

Second message — one compact checklist:
3. **The claim you believe.** Their one-sentence instinct for why
   customers should pick you — the draft tests it against evidence.
4. **Constraints.** Words legal/brand won't allow, category terms
   already committed to, tone.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Positioning & Messaging:
<product/feature>" and `content_markdown` structured as:

- `# <Title>`
- `## Positioning Statement` — the classic frame, every slot filled
  deliberately: "For <target> who <need>, <product> is a <category>
  that <key benefit>. Unlike <primary alternative>, it
  <differentiator>." Under it, one line per slot on why that choice
  (and what was rejected for it).
- `## Category Choice` — the tradeoff made explicit: the category
  you claim, what it makes easy (instant comprehension) vs what it
  costs (inherited comparisons), and the rejected alternative
  category.
- `## Messaging Hierarchy` — 2-4 pillars. Per pillar: the message
  (one sentence in customer language), then its proof points —
  each a real capability, metric, or customer evidence quoted or
  cited from a source. A pillar with no sourced proof point moves
  to "Aspirational" (below) — it cannot ship as a message.
- `## Aspirational (not yet claimable)` — messages the team WANTS
  that the evidence doesn't yet support, each with what would make
  it claimable. Honest parking beats quiet overclaiming.
- `## Competitive Contrast` — how each pillar fares against the
  named alternative, from the competitive doc only; where the
  competitor is genuinely stronger, say so — sales will hear it
  from prospects anyway.
- `## Message Don'ts` — claims to avoid (legal/brand constraints,
  overclaims the evidence can't carry, terms the competitor owns).
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose a `type=decision` entry (the
  positioning choice, IF approved) and `type=product` (the pillar
  set). Proposals until saved in Phase 3 — never mark one "Saved"
  in the doc.

### Depth guardrails

- **Proof points exist or the pillar doesn't ship.** Every proof
  point is a capability, metric, or quote from a source, cited
  inline. Inventing a stat, a customer quote, or a "2x faster"
  claim to prop a pillar is the workflow's cardinal failure.
- **The differentiator must survive the competitive doc.** Before
  claiming "unlike X", check the landscape doc — if the competitor
  plausibly claims the same thing, the differentiator is generic;
  pick the one they can't say.
- **Customer language over company language.** Messages use words
  from research notes and real quotes where sources have them —
  never internal feature names the target wouldn't recognize.
- **Segment choices come from the strategy.** The target slot
  matches the strategy doc's chosen segment; positioning that
  quietly widens or switches the segment is a flagged conflict,
  not a creative liberty.
- **Named customers need clearance.** Citing a customer by name in
  outward-facing messaging is flagged as needing permission unless
  a source records approval.
- **A prospect is not a win.** Evidence from an account that is
  evaluating, trialing, or in an open deal is framed as exactly that
  ("Northwind, in evaluation, told us…"), never as a closed win
  ("chose us over EchoMetrics") — closed-win language requires a
  source that records the win. Overstating a live deal as won is a
  proof point sales will get caught on.
- **Scrub internal IDs from an outward doc.** Positioning is
  customer-facing: never leak a fixture/planted-fact label (PF-19),
  tracker code, or memory annotation into it — cite the underlying
  fact in plain language.
- **One follow-up per thin answer.** If the alternative or the
  segment is vague, ask at most ONE follow-up, then draft with what
  you have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "positioning_messaging"`
- `document_id: <slug>`
- `summary_for_user: <one line: target, category choice, pillar count>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=decision` for the approved positioning choice;
`type=product` for the pillar set): one short confirmation listing
the entries, then save what the user okays. Then the skill completes.
