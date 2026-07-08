---
name: launch-plan
description: Draft a launch/GTM brief — launch tier, audience and positioning, readiness checklist, channel plan, success metrics, and rollback criteria.
slash_command: launch-plan
trigger_keywords: ["launch plan", "launch brief", "plan the launch", "go to market plan", "gtm plan", "launch checklist"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Launch-Plan Workflow

You are drafting a launch plan. The deliverable is a markdown brief a
team can execute against: the launch's tier and audience, an honest
readiness checklist, the channel/comms plan, success metrics, and the
rollback criteria nobody wants to need. Release-notes covers what
shipped; this doc is the plan to get there.

## Phase 1: Intake

FIRST, before asking anything (if the thing being launched wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — launch timelines anchor to today.
2. Call `RecallMemory` with the launch as the query, once each for
   `type=product` (what's shipping, success metrics, beta state),
   `type=decision` (committed dates, gates, or sequencing this launch
   must honor), `type=stakeholder` (key customers, design partners,
   execs with skin in the launch), and `type=lessons` (what past
   launches taught). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) the feature's PRD (success
   metrics, scope), (b) the roadmap (committed timing and sequencing),
   (c) quality-gate or readiness docs — a documented ship gate is
   rollback-criteria gold — and (d) positioning/competitive docs.
   `ReadDocument` what you find.
4. Present what you found in 2-3 bullets ("Here's what I have on the
   <launch> — correct anything wrong"), then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
any committed dates or sequencing you found, the success metrics with
their sourced baselines, and the readiness state per workstream —
and end your turn so the user can steer before you draft.

First message:
1. **What's launching, to whom, roughly when?** Scope, audience, and
   any date already committed (only dates from sources or the user go
   in the plan).
2. **How big a deal is this?** Their instinct on tier — full-court
   press vs quiet rollout — and why.

Second message — one compact checklist:
3. **Readiness.** What's done, in flight, or not started across
   product, docs, support, sales, marketing — pointers to docs are
   fine.
4. **Success and failure.** What result makes this launch a win, and
   what signal would make them pull it back.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Launch Plan: <launch>" and
`content_markdown` structured as:

- `# <Title>`
- `## Launch Summary & Tier` — what ships, the recommended tier with
  one line of reasoning, and the timing status (committed date from a
  source, or "date TBD — pending <what>").
- `## Audience & Positioning` — who this is for and the one-paragraph
  story, grounded in research/competitive docs where they exist.
- `## Readiness Checklist` — table: **Workstream | What must be true |
  Owner | Status**. Owners and statuses come from sources or the user;
  unknowns are "owner TBD" / "status unknown" — never guessed.
- `## Channel & Comms Plan` — where the launch shows up (in-app,
  email, blog, sales outreach, community), each with its audience and
  its one job.
- `## Success Metrics` — 2-4 metrics with baseline and target.
  Baselines verbatim from sources; a target without a source is
  labeled "proposed target" with its reasoning.
- `## Rollback / Hold Criteria` — the testable conditions that pause
  or roll back the launch, and who makes the call. Build on
  documented quality gates where they exist.
- `## Timeline` — milestones leading to launch. Only sourced or
  user-given dates; relative sequencing ("gate review → partner
  comms → GA") when dates don't exist yet.
- `## Risks` — what could sink the launch, including any
  `type=lessons` pattern that applies.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose `type=product` (tier, date if
  committed, success metrics) and `type=decision` entries (the
  go/no-go and rollback rules, IF approved). Proposals until saved in
  Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Never invent a date or an owner.** Dates and names come from
  sources or the user; everything else is "TBD" with what unblocks
  it. A plan with honest TBDs is executable; one with invented dates
  is a trap. Squads and teams are not owners unless a source assigns
  them to that workstream — "owner TBD" beats a plausible team name.
- **Metric names are copied, not coined.** Report a metric under the
  exact name and scope its source uses — never relabel a company-wide
  metric as a segment metric (or vice versa) because the move is
  concentrated there; write "company-wide WAU, dip driven by
  mid-market accounts", not "Mid-Market WAU".
- **Rollback criteria must be testable.** "If quality issues arise"
  is not a criterion; "digest groundedness failures exceed the gate
  for two consecutive days" is. Tie each to a metric or gate from the
  sources where possible.
- **Readiness is reported, not assumed.** Mark a workstream done only
  if a source or the user says so. An empty-looking checklist is
  information — it tells the team what the launch is waiting on.
- **The tier is a recommendation.** State it with reasoning
  (audience size, revenue stakes, strategic weight from the sources)
  and let the review make it final.
- **Protect committed sequencing.** If a `type=decision` memory or the
  roadmap commits timing or ordering (a deferred integration, a gated
  GA), the plan honors it or explicitly flags the conflict — never
  silently reschedules it.
- **One follow-up per thin answer.** If readiness or success metrics
  are vague, ask at most ONE follow-up, then draft with what you
  have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "launch_plan"`
- `document_id: <slug>`
- `summary_for_user: <one line: launch, tier, timing status>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for tier/date/metrics; `type=decision`
for approved go/no-go and rollback rules): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
