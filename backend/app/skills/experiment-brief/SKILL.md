---
name: experiment-brief
description: Design an A/B test or experiment properly — falsifiable hypothesis, variants, primary and guardrail metrics, runtime, and a pre-registered decision rule.
slash_command: experiment-brief
trigger_keywords: ["experiment brief", "design an experiment", "experiment design", "ab test plan", "a/b test plan", "design an ab test", "design an a/b test"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Experiment-Brief Workflow

You are designing an experiment. The deliverable is a markdown brief
that prevents the classic failures — no hypothesis, no decision rule,
peeking early, shipping on noise. The brief is complete only when the
decision rule is written down BEFORE the experiment starts; that's
the entire point of pre-registration.

## Phase 1: Intake

FIRST, before asking anything (if the change being tested wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — runtime windows and check dates anchor to today.
2. Call `RecallMemory` with the change as the query, once each for
   `type=product` (current metric baselines, past experiments on this
   surface), `type=decision` (standing experiment rules — minimum
   runtimes, no-peeking policies — the brief must honor), and
   `type=lessons` (past experiment failures and misreads). If a typed
   pull returns nothing, try one broader `SearchMemories` query, then
   move on — do not stall.
3. Call `ListDocuments` and look for (a) a metrics or experiment-log
   doc — baselines and standing rules live there, (b) the PRD or
   research behind the change being tested. `ReadDocument` what you
   find.
4. Present what you found in 2-3 bullets ("Here's what I have on the
   <change> experiment — correct anything wrong"), then ask ONLY
   what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **The change and the belief.** What changes, and what do they
   believe it will do, for whom?
2. **The primary metric.** The ONE number that decides this
   experiment, and where its baseline lives.

Second message — one compact checklist:
3. **Audience and traffic.** Who's eligible, roughly how many per
   week — or "unknown," which the brief handles honestly.
4. **The stakes.** What ships if it wins, what it must not break
   (candidate guardrail metrics).

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Experiment Brief: <name>"
and `content_markdown` structured as:

- `# <Title>`
- `## Hypothesis` — one falsifiable sentence: "If we <change>, then
  <primary metric> will <direction, size> because <mechanism>." The
  expected size comes from the user or a source analog, labeled as an
  expectation.
- `## Change & Variants` — control vs treatment(s), described
  precisely enough to build. One treatment unless the user insists;
  every extra variant divides the traffic.
- `## Primary Metric` — the ONE decision metric: definition, baseline
  verbatim with its source named, and the target/expected effect
  labeled as such. No baseline on record → "baseline unknown —
  capture before start" as a launch precondition.
- `## Guardrail Metrics` — 2-4 metrics that must not degrade, each
  with its current sourced value (or "unmeasured — instrument
  first") and the degradation level that trips it.
- `## Audience & Split` — who's eligible, the allocation (e.g.
  50/50), and exclusions.
- `## Runtime & Sample Size` — the honest version: minimum runtime
  honoring any standing rule from the sources, and expected sample
  from sourced traffic numbers. If traffic/variance inputs are
  missing, write "sample-size calculation needs <inputs> — get them
  before start"; NEVER fabricate a power analysis.
- `## Pre-Registered Decision Rule` — the heart of the brief: the
  check date (from runtime + `TimeCheck`), and the explicit rule —
  ship if <threshold>, kill if <threshold>, iterate otherwise — plus
  "no reads before the check date." A brief without this section is
  unfinished.
- `## Results Write-Up (fill at check date)` — a stub table the team
  fills later: metric readings, verdict against the rule, decision
  taken. Leave it empty — never pre-fill projected results.
- `## Risks` — contamination, seasonality, novelty effects — only
  those that plausibly apply, each with a mitigation.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose a `type=decision` entry (the
  pre-registered rule + check date, once approved) and `type=product`
  (the experiment's existence and its baselines). Proposals until
  saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Baselines are copied, never estimated.** Every current-value
  number traces verbatim to a doc, memory, or the user. A missing
  baseline becomes a launch precondition, not a plausible guess.
- **One primary metric.** Multiple decision metrics is how teams
  p-hack their way to shipping; everything else is a guardrail. If
  the user wants two, make them pick — that's a real conversation,
  not a formatting choice.
- **The decision rule is pre-registered or the brief is unfinished.**
  Ship/kill/iterate thresholds and the check date are written before
  launch. Refuse to leave this section as "we'll see how it looks."
- **Honor standing experiment rules.** If memory or a doc records a
  minimum-runtime or no-peeking rule, the brief cites and applies
  it — proposing a shorter run than a logged rule allows is a flagged
  conflict, not a default.
- **No fabricated statistics.** Sample sizes, power, and significance
  claims appear only when their inputs exist in the sources; showing
  the missing-inputs list is the honest alternative and is always
  acceptable.
- **One follow-up per thin answer.** If the metric or audience is
  vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns as launch preconditions.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "experiment_brief"`
- `document_id: <slug>`
- `summary_for_user: <one line: change, primary metric, check date>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=decision` for the pre-registered rule;
`type=product` for the experiment record): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
