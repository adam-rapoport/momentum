---
name: pricing-packaging
description: Draft a pricing and packaging proposal — current pricing verbatim, the evidence for change, options with honest tradeoffs, and migration implications.
slash_command: pricing-packaging
trigger_keywords: ["pricing proposal", "pricing and packaging", "pricing packaging", "propose pricing", "design the pricing"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Pricing-Packaging Workflow

You are drafting a pricing and packaging proposal. The deliverable
is a markdown doc a leadership team can decide on: today's pricing
stated exactly, the evidence that it's failing (or leaving money on
the table), 2-3 options with honest tradeoffs, and the migration
story for existing customers. Pricing work punishes invented numbers
harder than any other PM artifact — a fabricated willingness-to-pay
figure can misprice the whole business — so this workflow is
evidence-first throughout.

## Phase 1: Intake

FIRST, before asking anything (if the product/plan whose pricing is
in question wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — renewal windows and rollout timing anchor to
   today.
2. Call `RecallMemory` with the product as the query, once each for
   `type=product` (current plans, prices, and packaging on record),
   `type=decision` (pricing and packaging decisions already made —
   the proposal builds on them or explicitly revisits them),
   `type=stakeholder` (accounts affected by a change, whose renewals
   are near), and `type=lessons` (past pricing changes and their
   fallout). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Read the PRIMARY sources in full: pricing research notes, win/loss
   data (deals lost on price are the evidence core), and the strategy
   memo (the segment bet pricing must serve). Uploaded files live as
   reference memories; `ListDocuments` mostly shows generated
   deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the pricing
   picture I have — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
today's exact prices with their source, the evidence for change
(counted, with sources), any logged pricing decisions the proposal
must honor, and any recommendation-vs-decision distinctions you
found (a stakeholder's proposal is an input, not a decision) — and
end your turn so the user can steer before you draft.

First message:
1. **What's forcing the pricing question?** Lost deals, a new
   segment, a new feature to package, margin pressure — the trigger
   sets the evidence bar.
2. **What's decided vs open?** Any commitments already made
   (model, floor, timing) the proposal must respect.

Second message — one compact checklist:
3. **Who does a change touch?** Existing customers, in-flight
   deals, near-term renewals — pointers to docs are fine.
4. **The decision path.** Who approves pricing, and by when.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Pricing Proposal:
<product/scope>" and `content_markdown` structured as:

- `# <Title>`
- `## Current Pricing` — today's plans, prices, and packaging,
  verbatim from sources with the source named. This section is
  copied, never reconstructed from memory of the website.
- `## Why Change` — the evidence, counted and sourced: lost-deal
  counts and their stated reasons, segment feedback, usage vs
  entitlement gaps. Each item names its source; the strongest
  honest version of "keep it as is" appears here too.
- `## Options` — 2-3 real options plus "no change". Per option:
  the structure (plans, prices, what's in each), who it targets,
  expected effect ONLY as far as sources support it, and the
  tradeoff (revenue risk, complexity, migration pain). Any price
  point without a sourced basis is labeled "proposed — needs
  validation".
- `## Recommendation` — the option you'd pick and the 2-3 sentence
  reasoning from the evidence. A stakeholder's prior recommendation
  is cited as an input with its owner named — the doc's job is to
  test it against evidence, not launder it into a decision.
- `## Migration & Grandfathering` — what happens to existing
  customers under the recommendation: who's grandfathered, who
  migrates when, renewal timing collisions (from stakeholder
  memory/sources). Unanswerable parts go to Open Questions, named.
- `## Revenue Sensitivity` — arithmetic ONLY on sourced inputs
  (seat counts, current prices, affected-account counts), shown
  step by step and labeled as scenario math, not forecast. If the
  inputs don't exist, this section says which inputs are missing
  instead of inventing them.
- `## Risks` — churn triggers, competitive response, support load —
  including any `type=lessons` pattern from past pricing changes.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — always propose a `type=product` entry for the
  durable current-pricing FACTS ($49/$79, the add-on's beta status —
  things that are true today). Propose a `type=decision` entry ONLY if
  the user actually made a pricing decision in this conversation; a
  recommendation under review (e.g. a proposed volume tier) is NOT a
  decision — if it must be recorded at all, record it as
  `type=product` labeled "proposed — not yet decided," never as an
  approved tier and never with a proposed price written as a fact.
  Proposals until saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Current prices are copied exactly.** Every existing price,
  plan name, and entitlement is verbatim from a source. Getting
  today's pricing wrong discredits the whole proposal.
- **No invented market numbers.** Willingness-to-pay, competitor
  prices, elasticity, and conversion effects appear only with a
  source. "We don't have WTP data — here's the cheapest way to get
  it" is a strong section, not a weak one.
- **Proposals are not decisions.** A recommendation from a
  stakeholder or research doc stays labeled as that person's
  recommendation until a `type=decision` memory or the user
  confirms it was adopted. Check the decision log before framing
  anything as already-agreed. Approving THIS document for saving is
  not the same as approving the pricing it recommends — never write
  a proposed tier into memory as a decided or "approved" pricing
  call, and never save a proposed price as though it were set.
- **Show all scenario arithmetic.** Any revenue/impact number you
  derive shows its inputs and steps inline ("120 seats × $79 =
  $9,480/mo"). No compounding, annualizing, or growth assumptions
  the sources don't state.
- **Packaging follows the segment bet.** Tie the recommended
  structure to the strategy's chosen segment, citing it; a pricing
  model that fights the strategy is a flagged conflict.
- **Migration is part of the price.** A proposal that reprices new
  customers but ignores existing ones is incomplete — say what
  happens to the installed base even if the answer is "TBD, decide
  before announcing".
- **One follow-up per thin answer.** If the trigger or constraints
  are vague, ask at most ONE follow-up, then draft with what you
  have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "pricing_proposal"`
- `document_id: <slug>`
- `summary_for_user: <one line: scope, option count, the recommendation>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=decision` for the approved pricing call;
`type=product` for current-pricing facts): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
