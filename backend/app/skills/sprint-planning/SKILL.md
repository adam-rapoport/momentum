---
name: sprint-planning
description: Plan a sprint — scope candidate work against real capacity, set a sprint goal, and split committed vs stretch.
slash_command: sprint-planning
trigger_keywords: ["sprint planning", "plan the sprint", "sprint plan", "scope the sprint"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Sprint-Planning Workflow

You are planning a sprint. The deliverable is a markdown sprint plan
the team can commit to: a testable sprint goal, committed scope that
provably fits capacity, and an honest list of what is NOT happening.
The forward-looking twin of the sprint-review skill.

## Phase 1: Intake

FIRST, before asking anything (if the sprint identifier wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — sprint date ranges anchor to today.
2. Call `RecallMemory` with the sprint/product context as the query,
   once each for `type=product` (active initiatives, carryover, beta
   commitments), `type=team` (capacity patterns, velocity, ceremonies),
   `type=decision` (commitments this sprint must protect — deferred
   integrations, gated launches), and `type=lessons` (estimation and
   scoping patterns from past retros — they belong in this plan's
   risks). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Call `ListDocuments` and look for (a) planning inputs for this
   sprint (backlog/capacity notes), (b) the previous sprint's review
   doc (title starts with "Sprint Review:") — its Action Items and
   slipped work feed this plan — and (c) a previous "Sprint Plan:" doc
   for format continuity. `ReadDocument` what you find. Planning from
   the actual backlog doc beats re-asking the user to retype it.
4. Present what you found in 2-3 bullets ("Here's what I have going
   into Sprint N — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **Which sprint, and the date range?**
2. **Capacity.** Points (or person-days) actually available — after
   PTO, holidays, on-call, and recurring taxes. If they only know the
   usual number, ask what's different this sprint.

Second message — one compact checklist:
3. **Candidate work.** The backlog items in contention, with estimates
   if they exist. A pasted list or a pointer to a doc is fine.
4. **The one thing.** If only one outcome survives the sprint, what
   must it be? (This becomes the sprint goal.)

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Sprint Plan: <sprint name>
(<date range>)" and `content_markdown` structured as:

- `# <Title>`
- `## Sprint Goal` — ONE sentence the team can test at sprint end
  ("did we or didn't we?"). A goal is not a list of items; if the user
  gave a list, distill the outcome and put the list in scope.
- `## Capacity` — available points and why ("36 points, down from 40:
  one engineer PTO + audit interviews"), plus recent velocity quoted
  verbatim from its source for context.
- `## Committed Scope` — table: **Item | Squad/Owner | Points | Why
  now**. End with the arithmetic on its own line: "Committed total: X
  of Y available." X MUST be ≤ Y.
- `## Stretch` — 2-3 items max, explicitly not commitments: first in
  if the sprint runs ahead, first cut when it doesn't.
- `## Not This Sprint` — named cuts with one line of why. The honest
  displacement list is what makes the commitment credible.
- `## Carryover` — anything inherited from last sprint, marked as such.
- `## Last Retro's Action Items` — each one: which land in this plan
  (and where), which don't (and why). Omit only if there was no retro.
- `## Risks & Dependencies` — what could sink the goal, including
  external dependencies and any `type=lessons` pattern that applies.
- `## Memory Updates` — propose `type=product` (sprint goal + committed
  scope) and `type=team` (capacity pattern, if durable) entries. They
  are proposals until saved in Phase 3 — never mark one "Saved" in the
  doc.

### Depth guardrails

- **Never invent an estimate.** Points come verbatim from the user or
  a document. An unestimated item enters as "unestimated — needs
  sizing" and cannot be committed; committing unsized work is the #1
  way sprints die.
- **The committed total must fit capacity — show the arithmetic.** Sum
  the committed column yourself, verify it against the stated capacity,
  and write both numbers. If candidates exceed capacity, move the
  overflow to Stretch or Not This Sprint and say so — never plan to
  the hope number.
- **Quote velocity verbatim** ("completed 31 / 38 / 34 the last three
  sprints"). Never derive an average with more precision than the
  source, and never use velocity to inflate stated capacity.
- **Never subdivide capacity by squad unless the source provides the
  split.** Capacity is one number until the planning inputs break it
  down; an invented per-squad allocation ("~14 Triage / ~22 Insights")
  is fabricated arithmetic. If the user needs a split, ask for it or
  mark it "split unknown".
- **Protect logged commitments.** Check `type=decision` memory: if a
  decision committed something this sprint must enable (a deferred
  integration's start date, a gated launch), the plan either protects
  it — say where — or explicitly flags that it doesn't and why that
  needs a decision.
- **Stretch is not a parking lot.** More than 3 stretch items means
  the plan is dodging a cut; move the rest to Not This Sprint.
- **Sequencing matters.** If item B needs item A, the plan says so;
  if the dependency crosses squads, name both owners.
- **One follow-up per thin answer.** If capacity or an estimate is
  vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns — an imperfect plan the team can react to beats a
  stalled intake.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "sprint_plan"`
- `document_id: <slug>`
- `summary_for_user: <one line: sprint, goal, committed X of Y points>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the sprint goal + committed scope;
`type=team` for durable capacity patterns): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
