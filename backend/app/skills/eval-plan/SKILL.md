---
name: eval-plan
description: Turn an AI feature into an evaluation plan — failure taxonomy from real examples, pass/fail rubrics, grader prompts, and a ship gate.
slash_command: eval-plan
trigger_keywords: ["eval plan", "evaluation plan", "write evals", "draft evals", "design evals", "plan evals", "eval rubric"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Eval-Plan Workflow

You are writing an evaluation plan for an AI feature. The deliverable
is a markdown doc an eval owner can run: what "good" looks like, a
failure taxonomy grounded in real logged examples, graded rubrics with
usable judge prompts, and an explicit ship gate. Evals are the
acceptance criteria of AI features — vague ones are worthless.

## Phase 1: Intake

FIRST, before asking anything (if the feature under evaluation wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — eval-set refresh cadences and gate dates anchor
   to today.
2. Call `RecallMemory` with the feature as the query, once each for
   `type=product` (what the feature does, success metrics, quality
   thresholds already set), `type=decision` (existing quality gates or
   review policies the plan must honor), `type=team` (who owns model
   quality and evaluation), and `type=lessons` (known failure patterns).
   If a typed pull returns nothing, try one broader `SearchMemories`
   query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) a failure-example log or
   quality/eval doc for this feature, (b) the feature's PRD or spec —
   its intended behavior and success metrics are the baseline the
   evals protect. `ReadDocument` what you find. A logged failure
   taxonomy beats anything you could invent.
4. Present what you found in 2-3 bullets ("Here's what I have on
   <feature> — correct anything wrong"), then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **What does the feature do, and what must never happen?** The
   intended behavior and the unacceptable failures.
2. **What real failures have you seen?** Logged examples, a failure
   doc, or "none logged yet" — that answer changes the plan's shape.

Second message — one compact checklist:
3. **Existing thresholds.** Any quality bar already decided (gate
   scores, blocking rules), or is this plan proposing the first one?
4. **Who runs it.** The eval owner, and when evals run (pre-ship gate,
   regression cadence, both).

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Eval Plan: <feature>" and
`content_markdown` structured as:

- `# <Title>`
- `## Feature & Intended Behavior` — one paragraph: what it does, for
  whom, and the success metric it serves, quoted from the PRD/spec.
- `## What Good Looks Like` — 3-5 concrete properties of a passing
  output, each testable ("every claim traces to the source thread"),
  not aspirational ("high quality").
- `## Failure Taxonomy` — table: **Class | Frequency | Example |
  Detection**. Classes and counts come from the logged examples,
  quoted verbatim. Order by severity × frequency.
- `## Eval Set` — source, size, composition rules (what mix of cases
  and why), and refresh cadence. Existing set facts verbatim; a
  proposed new set labeled as a proposal.
- `## Rubrics & Graders` — per failure class: the pass/fail rubric,
  then the grader prompt as a fenced block ready to paste into an
  LLM-as-judge. Each prompt states the rubric explicitly and demands a
  binary verdict plus a quoted-evidence field. Note the human
  spot-check rate.
- `## Ship Gate` — the explicit rule: which scores, which thresholds,
  what blocks outright. One unambiguous sentence per condition.
- `## Runbook` — when evals run, who owns the judge prompts, where
  results land, and what happens on a gate failure.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose `type=product` (the ship gate +
  golden-set facts) and `type=decision` entries (a newly agreed gate or
  blocking rule). They are proposals until saved in Phase 3 — never
  mark one "Saved" in the doc.

### Depth guardrails

- **The taxonomy comes from logged failures only.** Every class,
  count, and example traces to a source document or the user. If no
  failures are logged yet, say so in the doc and present the taxonomy
  as hypotheses to validate — clearly labeled, with no invented counts
  or example quotes.
- **Thresholds are sourced or labeled proposed.** An existing gate is
  quoted verbatim. A new threshold is a proposal with one line of
  reasoning ("start at X, tighten after two clean runs") — never
  presented as an established bar.
- **Grader prompts must encode the rubric.** A judge prompt that says
  "check if the output is accurate" is a failed prompt; it must state
  the specific rule, the verdict format, and require quoted evidence
  from the source.
- **Honor existing quality decisions.** If `type=decision` memory or a
  doc records a blocking rule or review policy, the plan builds on it
  and cites it — a plan that silently relaxes an existing gate is
  wrong.
- **One primary gate metric.** More than ~2 gate conditions means the
  gate is a wishlist; extras go to the runbook as monitored metrics.
- **One follow-up per thin answer.** If failure examples or thresholds
  are vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "eval_plan"`
- `document_id: <slug>`
- `summary_for_user: <one line: feature, taxonomy size, the ship gate>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the gate + eval-set facts;
`type=decision` for a newly agreed gate): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
