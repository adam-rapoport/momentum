---
name: sprint-review
description: Run a structured sprint retrospective — what shipped, what slipped, learnings, and action items.
slash_command: sprint-review
trigger_keywords: ["sprint review", "sprint retro", "sprint retrospective", "run a retro", "retro for sprint"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Sprint-Review Workflow

You are running a structured sprint retrospective. The output is a
markdown doc the user (or their team) can read and act on.

## Phase 1: Intake

Ask one at a time, skipping any the user already supplied:

1. **Which sprint?** Sprint number/name, or the date range covered.
2. **Sprint goal.** What was the headline objective? If they don't
   remember, ask what mattered most.
3. **What shipped.** A list of features / chunks / PRs that landed.
   Bullet list is fine; commit titles are fine.
4. **What slipped.** Anything that was planned but didn't ship — and
   their best read on why (capacity, dependency, scope creep, …).
5. **Notable surprises.** Anything that changed mid-sprint — a bug
   discovered, a stakeholder ask, a tech detour.

Pull `type=project` (active sprint context, ongoing initiatives) and
`type=decision` (decisions made this sprint that should be recorded)
from memory using the sprint identifier as a query.

If past sprints have left `type=lessons` entries, pull those — recurring
patterns ("estimates always slip on integration work") belong in this
retro's Themes section.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Sprint Review: <sprint name>
(<date range>)" and `content_markdown` structured as:

- `# <Title>`
- `## Sprint Goal` — one sentence
- `## What Shipped` — bullets, each with one-line context (not just a
  PR title)
- `## What Slipped` — bullets, with the *why* attached to each item
- `## Surprises` — what came up mid-sprint that wasn't in the plan
- `## Themes / Learnings` — 2-4 patterns worth carrying forward (the
  honest read, not generic platitudes)
- `## Action Items` — concrete things for next sprint, each with an
  owner if known
- `## Memory Updates` — flag any `type=lessons` or `type=project`
  entries the user should add (you can suggest the wording)

### Depth guardrails

A retro that just lists items is a status report; a retro that pattern-
matches is the artifact worth re-reading later. Hold yourself to:

- **Every "Slipped" item names a cause, not a symptom.** "Auth migration
  didn't land" is a fact; "Auth migration didn't land — vendor SDK
  changed mid-sprint and we lost a day to the reroute" is a learning.
- **Themes are 3-5 sentences each.** If a theme is one line, it's a
  bullet, not a theme. Cut it or expand with a concrete example from
  this sprint.
- **Action Items are specific and dated.** "Improve estimation" means
  nothing; "Add a 'risk: external dependency' tag during sprint planning,
  starting Sprint N+1" is doable.
- **Be honest about wins.** A retro that only lists problems is wrong.
  Call out what worked so the team keeps doing it.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "sprint_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: which sprint, top 1-2 themes>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
