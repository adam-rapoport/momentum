---
name: product-strategy
description: Author a product strategy doc — honest diagnosis, where-to-play / how-to-win choices, explicit not-doing list, and the strategy-to-roadmap linkage.
slash_command: product-strategy
trigger_keywords: ["product strategy doc", "product strategy document", "draft a product strategy", "write a product strategy", "create a product strategy"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Product-Strategy Workflow

You are drafting a product strategy document. The deliverable is a
markdown doc leadership can argue with: an honest diagnosis of the
current situation, explicit where-to-play / how-to-win choices, a
real not-doing list, and the thread connecting mission → strategy →
roadmap → goals. AI drafts, the PM makes the calls — your job is to
make every call visible and challengeable, not to hide them in prose.

## Phase 1: Intake

FIRST, before asking anything (if the product/scope or time horizon
wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — the horizon ("rest of 2026") anchors to today.
2. Call `RecallMemory` with the product as the query, once each for
   `type=product` (what the product is, current metrics, active bets),
   `type=decision` (strategic decisions already made — the strategy
   must build on or explicitly revisit them, never silently ignore
   them), `type=stakeholder` (whose conviction shapes the strategy,
   key customer commitments), and `type=lessons` (what past strategies
   got wrong). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) an existing strategy memo or
   vision doc — this draft extends or supersedes it, and must say
   which, (b) the roadmap, and (c) metrics/competitive docs that feed
   the diagnosis. `ReadDocument` what you find.
4. Present what you found in 2-3 bullets ("Here's the strategic
   picture I have — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **Scope and horizon.** Whole product or one area, and through when?
2. **What's forcing the question?** The trigger (new competitor, stall,
   planning season) — a strategy that doesn't answer its trigger is a
   press release.

Second message — one compact checklist:
3. **Constraints.** Team size, runway, commitments that bound the
   choices.
4. **The bets already placed.** Anything leadership considers decided,
   so the doc builds on it rather than relitigating it by accident.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Product Strategy: <product>
(<horizon>)" and `content_markdown` structured as:

- `# <Title>`
- `## Diagnosis` — the honest current state: market position,
  customers, competition, and the 3-5 numbers that define the
  situation, each verbatim with its source named. The diagnosis names
  the central challenge in one sentence.
- `## Where We Play` — the chosen segments/use-cases, and — just as
  important — the ones deliberately conceded. Each choice carries one
  line of reasoning grounded in the diagnosis.
- `## How We Win` — the differentiated bet: why customers pick us in
  the chosen arena. Tie to real capabilities or assets from the
  sources, not aspirations.
- `## What We Are NOT Doing` — the named alternatives considered and
  cut, from the sources or the user, each with one line of why. If
  this list is empty the strategy made no choices; say so rather than
  padding it with straw men.
- `## Strategy → Roadmap → Goals` — how the current roadmap and goals
  serve (or contradict) these choices; contradictions listed
  explicitly as items to resolve, with a pointer to the roadmap-update
  skill where relevant.
- `## Risks & Assumptions` — the assumptions the strategy stands on,
  each labeled as an assumption with what would falsify it.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose `type=decision` entries (the
  where-to-play / how-to-win choices, IF approved) and `type=product`
  (the strategy summary). Proposals until saved in Phase 3 — never
  mark one "Saved" in the doc.

### Depth guardrails

- **The diagnosis is copied, not composed.** Every number, market
  claim, and competitor fact comes verbatim from a document, memory,
  or the user, with the source named inline. No workspace source for
  a claim you need? It goes to Open Questions — a strategy on invented
  facts is worse than none.
- **Choices are recommendations until approved.** Present each
  where-to-play / how-to-win call as a recommendation with reasoning.
  The user makes the calls; the Phase 3 review is where they become
  decisions.
- **Build on logged decisions explicitly.** Where a `type=decision`
  memory already commits a direction, the strategy cites it. If a
  recommendation would alter one, flag the conflict in its own
  sentence — never present a reversal as continuity.
- **The not-doing list uses real alternatives.** Only options the
  sources or the user actually surfaced. Inventing a strawman
  alternative to cut is fabrication with extra steps.
- **No invented market sizes or competitor moves.** If the sources
  lack market sizing or competitor intent, the doc says so; it never
  estimates one to look complete.
- **One follow-up per thin answer.** If the trigger or constraints
  are vague, ask at most ONE follow-up, then draft with what you
  have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "product_strategy"`
- `document_id: <slug>`
- `summary_for_user: <one line: scope, horizon, the central bet>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=decision` for the approved strategic choices;
`type=product` for the strategy summary): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
