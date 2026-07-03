---
name: sprint-review
description: Run a structured sprint retrospective — what shipped, what slipped, learnings, and action items.
slash_command: sprint-review
trigger_keywords: ["sprint review", "sprint retro", "sprint retrospective", "run a retro", "retro for sprint"]
required_tools: ["RecallMemory", "SearchMemories", "SaveMemory", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Sprint-Review Workflow

You are running a structured sprint retrospective. The output is a
markdown doc the user (or their team) can read and act on.

## Phase 1: Intake

FIRST, before asking anything (if the sprint identifier wasn't
supplied, ask that one question, then):

1. Call `RecallMemory` with the sprint identifier as the query, once
   each for `type=product` (active sprint context, ongoing initiatives),
   `type=decision` (decisions made this sprint), and `type=team`
   (capacity patterns, ceremonies). Also pull `type=lessons` —
   recurring patterns from past retros belong in Themes. If a typed
   pull returns nothing, try one broader `SearchMemories` query, then
   move on — do not stall.
2. Call `ListDocuments` and look for the previous sprint's review doc
   (title starts with "Sprint Review:"). If found, `ReadDocument` it
   and pull its Action Items. If not found, ask the user in one line
   whether last retro had action items.
3. Present what you found in 2-3 bullets ("Here's what I already have
   on Sprint 12 — correct anything wrong"), then ask ONLY the intake
   questions memory and the conversation haven't answered.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the user's opening message already covers
everything, go straight to Phase 2.

First message:
1. **Which sprint?** Sprint number/name, or the date range covered.
2. **Sprint goal.** What was the headline objective? If they don't
   remember, ask what mattered most.

Second message — one compact checklist answerable in a single reply:
3. **What shipped.** Features / chunks / PRs that landed. Bullet list
   is fine; commit titles are fine.
4. **What slipped.** Planned but didn't ship — and their best read on
   why (capacity, dependency, scope creep, …).
5. **Notable surprises.** Anything that changed mid-sprint — a bug
   discovered, a stakeholder ask, a tech detour.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Sprint Review: <sprint name>
(<date range>)" and `content_markdown` structured as:

- `# <Title>`
- `## Sprint Goal` — one sentence, plus a verdict on its own line:
  **Hit / Partially hit / Missed** — with one clause of why.
- `## Last Retro's Action Items` — each prior item with Done / Not
  done / Dropped and one line of context. Omit this section only if
  there was no prior retro.
- `## What Shipped` — bullets, each with one-line context (not just a
  PR title)
- `## What Worked` — 1-3 things the team should deliberately keep
  doing, each tied to a concrete moment this sprint (not "good
  teamwork")
- `## What Slipped` — bullets, with the *why* attached to each item
- `## Surprises` — what came up mid-sprint that wasn't in the plan
- `## Themes / Learnings` — 2-4 patterns worth carrying forward (the
  honest read, not generic platitudes)
- `## Action Items` — concrete things for next sprint, each with an
  owner if known
- `## Memory Updates` — propose `type=lessons` or `type=product`
  entries worth saving, with suggested wording. They are proposals
  until saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

A retro that just lists items is a status report; a retro that pattern-
matches is the artifact worth re-reading later. Hold yourself to:

- **Never invent specifics.** Every cause, date, name, and example must
  come from the user, memory, or a document. If a slipped item's cause
  is unknown, write "cause unconfirmed" and add an Action Item to find
  out — do not manufacture a plausible story.
- **Quote burndown/velocity numbers verbatim from the sprint notes**
  ("completed X of Y points"). Never recompute, invert, or derive a
  plan-vs-actual figure arithmetically — if the notes don't state it,
  it doesn't go in the doc.
- **Every "Slipped" item names a cause, not a symptom.** "Auth
  migration didn't land" is a fact; "Auth migration didn't land —
  vendor SDK changed mid-sprint and we lost a day to the reroute" is
  a learning.
- **Themes are 3-5 sentences each.** If a theme is one line, it's a
  bullet, not a theme. Cut it or expand with a concrete example from
  this sprint.
- **Action Items are specific and dated.** "Improve estimation" means
  nothing; "Add a 'risk: external dependency' tag during sprint
  planning, starting Sprint N+1" is doable.
- **Wins live in `## What Worked`.** A retro that only lists problems
  is wrong — call out what worked so the team keeps doing it.
- **One follow-up per thin answer.** If the user answers in one line
  and you need more for a cause or theme, ask at most ONE follow-up
  for that item, then draft with what you have — an imperfect retro
  shipped today beats a perfect one abandoned.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "sprint_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: which sprint, goal verdict, top theme>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=lessons` for retro takeaways, `type=product` for
roadmap-state changes): one short confirmation listing the entries,
then save what the user okays. Then the skill completes.
