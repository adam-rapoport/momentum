---
name: okr-planning
description: Draft quarterly objectives and key results tied to the strategy, with built-in quality checks — outcome not output, measurable, honest baselines.
slash_command: okr-planning
trigger_keywords: ["okr planning", "draft okrs", "write okrs", "set okrs", "plan okrs", "objectives and key results"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# OKR-Planning Workflow

You are drafting OKRs. The deliverable is a markdown doc a team can
commit to: 2-3 objectives that serve the strategy, key results with
honest baselines and measurable targets, and an explicit record of
what was deprioritized. Most OKRs fail the same few checks — outputs
dressed as outcomes, unmeasurable KRs, targets with no baseline — so
this workflow enforces those checks in the doc itself.

## Phase 1: Intake

FIRST, before asking anything (if the team/scope or quarter wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — "next quarter" resolves against today.
2. Call `RecallMemory` with the product/team as the query, once each
   for `type=product` (strategy bets, current baselines, existing
   targets), `type=decision` (commitments the OKRs must serve or
   protect), and `type=lessons` (how past goal cycles went wrong).
   If a typed pull returns nothing, try one broader `SearchMemories`
   query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) the strategy memo/doc — OKRs
   without a strategy to serve are a wishlist, (b) metrics docs with
   current baselines, (c) the roadmap, and (d) last quarter's OKRs or
   review (what carried, what was dropped). `ReadDocument` the
   PRIMARY sources in full — the uploaded memo, metrics, and roadmap
   docs — not just their memory snippets. Recognize generated docs by
   their deliverable-pattern titles ("OKRs:", "Product Strategy:",
   "Launch Plan:", "Sprint Plan:", "Metrics Review:", "Eval Plan:",
   "Experiment Brief:", "PRD:") — those are ASSISTANT OUTPUT, not
   primaries, no matter how on-topic they look. Primaries are the
   uploaded source materials (memos, notes, logs, exports). Read
   generated docs last, if at all; when a generated doc's number
   differs from a primary's, the primary wins and the discrepancy
   gets flagged. You are not ready to draft until you have read at
   least one uploaded primary in full.
4. Present what you found in 2-3 bullets ("Here's what I have going
   into <quarter> — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional for this skill:
post it — naming the strategy's standing numeric targets and the
baselines you'll use, each with its source — and end your turn so
the user can steer before you draft.

First message:
1. **Scope and quarter.** Whose OKRs (company, product org, one team)
   and for which quarter?
2. **The strategic priorities.** The 1-3 bets these OKRs must advance
   — from the strategy doc if one exists, otherwise from the user.

Second message — one compact checklist:
3. **Baselines.** Where current numbers live for the results that
   matter — doc pointers are fine.
4. **Non-negotiables.** Existing commitments (dates, customer
   promises, compliance) the OKRs must not contradict.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "OKRs: <scope> <quarter>"
and `content_markdown` structured as:

- `# <Title>`
- `## Strategy Link` — 2-3 sentences naming which strategic bets
  these OKRs serve, citing the strategy source — then a **Standing
  targets** list: every numeric target the strategy source sets, each
  with its disposition ("→ KR 1.2" or "not carried this quarter —
  <why>"). A target acknowledged in intake but absent here is a
  dropped commitment.
- `## Objectives` — 2-3 maximum. Each objective: one qualitative,
  outcome-shaped sentence a team could rally behind, plus one line on
  why now.
- Per objective, `### KRs` — table: **Key Result | Baseline | Target |
  How we'll measure | Owner**. 2-4 KRs per objective. Baselines
  verbatim from sources; no baseline on record → "baseline unknown —
  measure in week 1" (that's a legitimate KR state, an invented
  baseline is not). Owners only from sources or the user.
- `## Quality Checks` — the doc grades its own OKRs, one line each:
  (a) every KR an outcome, not a task/output; (b) every KR measurable
  with a named source; (c) targets ambitious relative to baseline —
  with the reasoning; (d) few enough to mean something. Each line
  cites its evidence (KR numbers, source names) — a check that names
  no evidence is a rubber stamp and fails. Where a check fails and
  the user insisted, say so honestly.
- `## Not This Quarter` — goals considered and deprioritized, from
  sources or the user, each with one line of why. The cut list is
  what makes the commit list credible.
- `## Risks & Dependencies` — what could sink these OKRs, including
  any `type=lessons` pattern from past cycles.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose `type=product` (the OKR set, once
  approved) and `type=decision` entries (an explicit deprioritization
  the user confirmed). Proposals until saved in Phase 3 — never mark
  one "Saved" in the doc.

### Depth guardrails

- **Never invent a baseline.** A KR's baseline is verbatim from a
  source or the user, or it's "baseline unknown — measure first."
  Targets against invented baselines are fiction with a percent sign.
- **Baselines and targets come from PRIMARY sources only.** Never
  take a baseline, target, renewal date, or stakeholder position from
  a previously generated document (strategy draft, launch plan,
  metrics review) — verify it in an uploaded primary or with the
  user. If only a generated doc has it, write "(per the <title> doc,
  unverified)" and do not build a KR on it. A number that changed
  meaning between a primary and a generated doc (a company-wide
  metric relabeled as a segment metric) is a fabrication to catch,
  not inherit. The tag is applied INLINE where the number appears,
  every time — and a generated doc is never described as a primary;
  misfiling one is itself a factual error.
- **Targets are proposals with reasoning.** Each target gets one line
  of why-this-number relative to its baseline ("58% now; 64% was the
  2025 level — recovering it is ambitious but precedented"). Never
  present a proposed target as an agreed one.
- **Outcome, not output.** "Ship feature X" is a roadmap item, not a
  KR; the KR is what shipping it changes. The Quality Checks section
  must actually catch these — rewrite or flag every output-shaped KR.
- **Every KR names its measurement source.** A KR nobody can measure
  ("improve quality") either gets a named metric and source or moves
  to the objective's narrative.
- **Align with logged targets and commitments.** If a strategy memo
  or `type=decision` memory already sets a target or commitment, the
  OKRs match it or explicitly flag the difference — never quietly
  restate a committed number as something else, and never silently
  DROP one: every numeric target in the source strategy appears in
  the doc, mapped to a KR or explicitly listed with why these OKRs
  don't carry it. The Quality Checks section must verify each
  baseline against a named primary source — a KR whose baseline
  can't cite one fails its own check.
- **2-3 objectives, hard cap.** More means priorities weren't chosen;
  push extras to Not This Quarter and say so.
- **One follow-up per thin answer.** If priorities or baselines are
  vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "okr_plan"`
- `document_id: <slug>`
- `summary_for_user: <one line: scope, quarter, objective count>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the approved OKR set;
`type=decision` for confirmed deprioritizations): one short
confirmation listing the entries, then save what the user okays.
Then the skill completes.
