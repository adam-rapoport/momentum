---
name: model-selection
description: Draft a model-selection decision memo — candidates scored on sourced capability, cost, latency, and risk, a weighting rationale, a recommendation, and the fallback with its flip condition.
slash_command: model-selection
trigger_keywords: ["model selection", "select a model", "choose a model", "compare models", "model selection memo"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Model-Selection Workflow

You are writing a model-selection decision memo — which model an AI
feature should run on. The deliverable is a markdown memo a tech lead
and PM can decide from: candidates scored on capability, cost, latency,
and risk (every number from a source), the weighting that matters for
THIS use case, a recommendation, and the fallback with the condition
that would flip it. Model selection punishes invented numbers hardest
of any AI-era doc: a fabricated price or context-window figure can pick
the wrong model and misprice the feature. Use the team's own measured
numbers only — never a spec you "know" about a real model.

## Phase 1: Intake

FIRST, before asking anything (if the feature/use case whose model is
in question wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — pricing and benchmark numbers age fast; date the
   memo and its inputs.
2. Call `RecallMemory` with the feature as the query, once each for
   `type=product` (what the feature does, the quality bar it must
   clear, the current model if one's in place), `type=decision`
   (prior model/build decisions the memo must honor — e.g. a
   build-in-house choice, a cost-alignment decision), `type=team`
   (who owns model quality and evaluation), and `type=lessons` (past
   model swaps and their fallout). If a typed pull returns nothing,
   try one broader `SearchMemories` query, then move on — do not stall.
3. Read the PRIMARY sources in full: the benchmark/options doc with
   the candidate numbers (cost, latency, context window, measured
   quality — these are the sourced figures the memo copies), and the
   feature's PRD or eval doc (the quality gate the pick must clear).
   Uploaded files live as reference memories; `ListDocuments` mostly
   shows generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here are the candidates and
   the numbers I have — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the candidate models with their sourced numbers, the quality bar they
must clear (with its source), and any logged decision the choice must
honor — and end your turn so the user can steer before you draft.

First message:
1. **What's the feature and the quality bar it must clear?** The
   use case and the non-negotiable quality threshold (a groundedness
   gate, an accuracy floor) — from a source if one exists.
2. **What are the candidates, and what's measured?** The models in
   contention and where the numbers live (a benchmark doc, vendor
   pricing, measured latencies) — or "not measured yet".

Second message — one compact checklist:
3. **What matters most here?** Quality, cost, latency, context window,
   data-residency — the ranking that drives the pick.
4. **The decision path.** Who owns the call, and by when.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Model Selection: <feature>"
and `content_markdown` structured as:

- `# <Title>`
- `## Decision & Context` — one paragraph: what model decision is
  being made, for what feature, the quality bar it must clear
  (sourced), and that this memo is an INPUT to a decision the owner
  makes — not the decision itself.
- `## Candidates` — table: **Model | Quality (on our set) | Cost |
  Latency | Context window | Key risk/unknown**. Every cell is copied
  from a source and says so; a cell with no measured number reads
  "unverified — needs measurement", never a guessed figure. Include
  the current/incumbent model as a row if there is one.
- `## What Matters Here` — the weighting for THIS use case, ranked,
  each tied to a sourced reason (e.g. "quality gate is non-negotiable
  — a fabricated quote auto-blocks; cost matters because AI Summaries
  is usage-billed, so per-digest cost scales with adoption"). The
  ranking, not just a list.
- `## Recommendation` — the pick and 2-3 sentences of reasoning that
  trace to the weighting and the sourced numbers. Show any arithmetic
  inline ("$6.00/1M tokens × ~8k tokens/digest = ~$0.048/digest").
  If the top candidate on cost fails the quality gate, say so — the
  gate wins.
- `## Fallback & Flip Condition` — the second choice, and the explicit
  condition that would change the decision (a gate failure in
  production, a price change, a latency regression, a volume threshold).
- `## How We'll Verify` — the pick isn't final until it clears the
  quality gate on the real eval set; name the metric, the owner, and
  point at the eval-plan skill for the full plan. A model memo without
  a verification step is a guess.
- `## Open Questions` — the numbers that are missing and how to get
  them (what to measure, on what set).
- `## Memory Updates` — propose a `type=product` entry for the sourced
  candidate facts (the current model, the measured numbers). Propose a
  `type=decision` entry ONLY if the user actually chose a model in this
  conversation; a recommendation still under review is recorded, if at
  all, as `type=product` labeled "proposed — not yet decided", never as
  an approved pick. Proposals until saved in Phase 3 — never mark one
  "Saved" in the doc.

### Depth guardrails

- **Every number is copied or labeled unmeasured.** Cost, latency,
  context window, and quality scores come verbatim from a source. A
  cell you can't source says "unverified — needs measurement". Never
  fill it with a figure you recall about a real-world model — the
  team's own measurements are the only currency here.
- **The quality bar is non-negotiable and sourced.** If a candidate
  misses the gate (e.g. groundedness below the sourced threshold), no
  cost or latency advantage overrides it. State the gate, its source,
  and which candidates clear it.
- **Show the cost arithmetic.** Any per-request/per-digest/monthly cost
  is derived step by step from sourced per-token prices and sourced
  volumes — no annualizing or growth assumptions the sources don't
  state.
- **A recommendation is not a decision.** The benchmark and your pick
  are inputs to a call the owner makes. Approving THIS memo for saving
  is not approving the model — never write the pick into memory as
  "chosen" or "approved" unless the user decided it here.
- **Name the fallback and the flip condition.** A memo with one option
  and no trigger-to-revisit isn't a decision aid — it's an opinion.
- **One follow-up per thin answer.** If the candidates or the bar are
  vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "model_selection"`
- `document_id: <slug>`
- `summary_for_user: <one line: feature, candidate count, the recommendation + fallback>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the candidate facts; `type=decision`
only for a model the user actually chose here): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
