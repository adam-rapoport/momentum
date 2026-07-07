---
name: metrics-review
description: Turn raw product numbers into a metrics scorecard — trends vs targets, honest why-hypotheses, and recommended actions.
slash_command: metrics-review
trigger_keywords: ["metrics review", "metrics readout", "metrics scorecard"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Metrics-Review Workflow

You are running a metrics review. The deliverable is a markdown
scorecard a team can act on: every number verbatim from its source,
deltas with the arithmetic shown, causes separated into confirmed vs
hypothesis, and recommendations tied to specific metrics. This is a
recurring ritual — continuity with the previous review is part of the
job.

## Phase 1: Intake

FIRST, before asking anything (if the period under review wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — "this month"/"last week" resolve against today.
2. Call `RecallMemory` with the product/period as the query, once
   each for `type=product` (targets, north-star and baseline metrics
   on record), `type=decision` (bets whose results these metrics
   measure), and `type=lessons` (recurring metric patterns and past
   misreads). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) metrics docs/exports covering
   the period, (b) the PREVIOUS review (title starts with "Metrics
   Review:") — its watch list and actions get followed up here — and
   (c) strategy/OKR docs that set the targets. `ReadDocument` what
   you find. Reviewing from the actual numbers doc beats asking the
   user to retype it.
4. Present what you found in 2-3 bullets ("Here's the data I have for
   <period> — correct anything wrong"), then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **Which metrics matter most this cycle?** The 3-6 headline metrics,
   or "use what the docs cover."
2. **Anything unusual this period?** Launches, incidents, seasonality
   — context that separates signal from noise.

Second message — one compact checklist:
3. **Targets.** Where do targets live (doc, OKRs, memory), or is a
   metric untargeted? Untargeted is a valid, reportable answer.
4. **Audience.** Team working session or leadership readout — it sets
   the depth of the "why" sections.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Metrics Review: <period>"
and `content_markdown` structured as:

- `# <Title>`
- `## TL;DR` — 2-3 sentences: the one metric that most needs
  attention, the one that's working, the recommended focus.
- `## Scorecard` — table: **Metric | Current | Prior / Baseline |
  Target | Delta | Status**. Every number verbatim with its source
  named (doc title or memory). No target on record → "no target set".
  Show the arithmetic for any delta you compute ("58% − 64% = −6
  pts").
- `## What Moved & Why` — per notable move: the change, then the
  explanation labeled either **confirmed** (a source states the
  cause) or **hypothesis** (your inference — say what evidence would
  confirm it). Never present a hypothesis in the voice of a fact.
- `## Off-Target` — metrics missing their target, with how far off
  and for how long (only if the sources show history).
- `## Recommended Actions` — 2-5 actions, each naming the metric it
  moves, the expected direction, and who'd own it (owner only from
  sources or the user).
- `## Watch List` — metrics not yet alarming but worth next cycle's
  attention, each with the threshold that would escalate it.
- `## Follow-ups From Last Review` — if a previous review exists:
  each action/watch item, and what happened to it. Omit only if
  there's no previous review.
- `## Open Questions` — data gaps ("no history for X — first period
  measured").
- `## Memory Updates` — propose `type=product` (durable metric facts:
  new baseline, confirmed trend) and `type=lessons` entries (a
  misread pattern worth remembering). Proposals until saved in Phase
  3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Copy, don't compute — and show any arithmetic you do.** Numbers
  come verbatim from sources. The only derived figures allowed are
  simple deltas between two sourced numbers, with the subtraction
  shown. Never derive rates, averages, or projections the source
  doesn't contain.
- **A trend needs at least two sourced points.** One data point is a
  level, not a trend; "first period measured" is the honest label.
  Never extrapolate a trajectory from a single reading.
- **Confirmed vs hypothesis is a hard line.** A cause is confirmed
  only if a source or the user states it. Your inference — however
  plausible — is a hypothesis and carries the label.
- **Never invent a target.** If no source sets one, the scorecard
  says "no target set" — proposing a target is allowed only in
  Recommended Actions, labeled as a proposal.
- **Segment-level claims need segment-level data.** Don't attribute
  an aggregate move to a segment/account unless a source makes the
  attribution.
- **One follow-up per thin answer.** If the data or the targets are
  vague, ask at most ONE follow-up, then draft with what you have,
  marking gaps in Open Questions.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "metrics_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: period, headline move, top action>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for durable metric facts; `type=lessons`
for misread patterns): one short confirmation listing the entries,
then save what the user okays. Then the skill completes.
