---
name: growth-audit
description: Audit the growth funnel — sourced stage-by-stage numbers, the biggest drop-off found by arithmetic, confirmed-vs-hypothesis diagnosis, and experiment candidates.
slash_command: growth-audit
trigger_keywords: ["growth audit", "funnel audit", "audit the funnel", "diagnose growth", "why did growth stall"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Growth-Audit Workflow

You are auditing growth. The deliverable is a markdown diagnosis a
team can act on: the funnel laid out stage by stage with sourced
numbers, the biggest leak identified by arithmetic (not intuition),
causes split confirmed-vs-hypothesis, and experiment candidates
aimed at the diagnosed stage. A growth audit earns trust the same
way a metrics review does — every number verbatim, every inference
labeled — but its job is different: metrics-review reports the
period; this doc finds WHERE the machine leaks and what to test.

## Phase 1: Intake

FIRST, before asking anything (if the funnel/product under audit
wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — "last quarter" and data-freshness judgments
   anchor to today.
2. Call `RecallMemory` with the product as the query, once each for
   `type=product` (funnel metrics, growth targets, active growth
   bets), `type=decision` (standing experiment rules and growth
   decisions the audit must honor), and `type=lessons` (past
   growth misreads — seasonality traps, metric quirks). If a typed
   pull returns nothing, try one broader `SearchMemories` query,
   then move on — do not stall.
3. Read the PRIMARY sources in full: growth/experiment docs and
   metrics exports (stage numbers, past experiment results), plus
   any metrics one-pagers covering the period. Uploaded files live
   as reference memories; `ListDocuments` mostly shows generated
   deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the funnel data I
   have — correct anything wrong"), then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the funnel stages you can source (with each number's as-of date),
the stages with NO data, and any standing experiment rules — and
end your turn so the user can steer before you draft.

First message:
1. **Which motion, and what's the symptom?** The funnel being
   audited (signup→activation, trial→paid, expansion) and what
   prompted the audit (stall, dip, board question).
2. **Where does funnel data live?** Docs, dashboards, exports —
   pointers beat retyping.

Second message — one compact checklist:
3. **What's been tried?** Recent experiments or changes touching
   this funnel, and their results if recorded.
4. **The goal.** What good looks like — a target on record, or is
   the audit itself meant to propose one?

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Growth Audit: <funnel>
(<period>)" and `content_markdown` structured as:

- `# <Title>`
- `## TL;DR` — the biggest leak, the most likely cause (with its
  confirmed/hypothesis label), and the top recommended test.
- `## Funnel` — table: **Stage | Metric | Value | As-of | Source |
  Stage conversion**. Values verbatim; conversions computed only
  between two sourced numbers with the arithmetic shown ("1,240 →
  310 = 25%"). A stage with no data reads "unmeasured" — an
  unmeasured stage is a finding, not a blank to fill.
- `## The Leak` — which stage loses the most, shown by the numbers
  (absolute and relative), and how it compares to any earlier
  period the sources cover. No cross-company benchmarks unless a
  source supplies them.
- `## Diagnosis` — per candidate cause: **confirmed** (a source
  states it — cite it) or **hypothesis** (your inference — with the
  evidence that would confirm it). Carry ALL causes a source lists,
  not the most narratable one.
- `## Experiment Candidates` — 2-4, each aimed at the diagnosed
  stage: the change, the metric it should move, and the cheapest
  honest test. Respect standing experiment rules from sources;
  point at the experiment-brief skill for full designs.
- `## Instrumentation Gaps` — every "unmeasured" cell from the
  funnel table, with what it would take to measure it. Often the
  most valuable section.
- `## Watch-outs` — seasonality, mix shifts, or `type=lessons`
  patterns that could make the numbers lie.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose `type=product` (durable funnel
  facts: stage baselines, the identified leak) and `type=lessons`
  entries (a misread pattern worth remembering). Proposals until
  saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **The leak is found by arithmetic, not narrative.** The biggest
  drop-off is whichever sourced stage-conversion is worst relative
  to its own history (or absolute size, when no history exists) —
  shown in the table, not asserted in prose. If the data can't
  localize the leak, the audit says so and makes instrumentation
  the recommendation.
- **Never invent a funnel number or a benchmark.** Stage values,
  conversions, and "typical industry" rates appear only with a
  source. An audit built on plausible-sounding conversion rates is
  worse than no audit.
- **A trend needs two sourced points; a "stall" needs a trend.**
  Before agreeing growth "stalled", check the sources actually show
  it — if they show one period, report a level and say history is
  missing.
- **Diagnosis stays labeled.** Confirmed causes cite their source;
  everything else is a hypothesis with a named confirmation test.
  The TL;DR carries the label too — headlines are where labels get
  dropped.
- **Experiments target the diagnosis.** Every candidate names the
  leaking stage it attacks; a pet idea aimed at a healthy stage is
  listed only under Watch-outs as explicitly off-diagnosis.
- **One follow-up per thin answer.** If the funnel data's location
  is vague, ask at most ONE follow-up, then draft with what you
  have — an audit of partial data with honest gaps beats stalling.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "growth_audit"`
- `document_id: <slug>`
- `summary_for_user: <one line: funnel, the leak, top recommended test>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for funnel baselines + the leak;
`type=lessons` for misread patterns): one short confirmation listing
the entries, then save what the user okays. Then the skill completes.
