---
name: user-story
description: Turn a vague problem statement or feature idea into structured user stories with acceptance criteria and edge cases.
slash_command: user-story
trigger_keywords: ["user story", "user stories", "write a user story", "draft user stories", "break this into stories"]
required_tools: ["RecallMemory", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# User-Story Workflow

You are turning a problem statement or feature idea into one or more
structured user stories that engineering can pick up. Output is a
markdown doc.

## Phase 1: Intake

Before asking anything:

- Call `RecallMemory` with `type=product` and `query=<the feature
  topic>`; also `RecallMemory` with `type=stakeholder` if a persona or
  segment is named. Skip any intake question memory already answers —
  confirm instead: "Memory says your core segment is returning buyers
  — writing for them unless you say otherwise." If memory returns
  nothing, just proceed to the questions.
- If this feature likely has a PRD or spec (the user mentions one, or
  you wrote one in this project), call `ListDocuments` and
  `ReadDocument` it. Derive the stories and acceptance criteria from
  its Scope and Success Metrics sections instead of re-interviewing
  the user; link the PRD under `## Notes`.

**Express lane.** If the opening message already covers the problem
and persona, or the user says "just draft it" / gives one-line
answers, stop interviewing. Draft with reasonable assumptions and add
an `**Assumptions:**` line under each story naming exactly what you
guessed, so the user can correct in review. Never ask more than 3
questions total before drafting.

Otherwise ask one at a time, skipping anything already supplied:

1. **Problem or feature.** What's the user-facing thing? Phrase it as
   a sentence ("Customers can't find past orders") not a label.
2. **Persona / user type.** Who has this problem? Be specific — "a
   user" is too vague. "A first-time buyer," "a returning power user,"
   "an admin managing 10+ teammates" are useful.
3. **Trigger / context.** When does this come up in their workflow?
   What were they trying to do that led here?
4. **Desired outcome.** What does success look like for the user?
   (Not "we ship the feature" — "the user finds the order in under
   30 seconds without contacting support.")

**Granularity — propose, don't ask.** Don't ask an open-ended "one
story or several?" If the ask is clearly bigger than one story,
propose a concrete split ("I'd cut this into 3 stories: search,
filters, export — sound right?") and let the user veto.

## Phase 2: Drafting

For a single story:

```
As a <persona>,
I want to <do thing>,
So that <I get outcome>.
```

For multiple stories, use the same shape per story under a parent
heading. Don't pad — if there's truly only one story, write one.

Call `WriteDocument` with `title` like "User Stories: <feature/problem>"
and `content_markdown`:

- `# <Title>`
- `## Problem` — one paragraph. Cite evidence if any exists: a
  support-ticket count, a funnel number, or a verbatim user quote
  (memory may have these). No evidence? Say so: "no data yet; based
  on PM judgment" — honesty keeps eng from over-trusting the premise.
- `## Persona` — who has this, why they have it, what they'd do today
  to work around it
- `## Story` for a single story (no numbered subheading); use
  `### Story N: <short title>` only under `## Stories` for multiple.
  For multiple stories: order them by suggested build sequence and tag
  each `**Priority:** P0/P1/P2` with a one-clause reason (e.g. "P0 —
  nothing else works without search indexing"). Per story:
  - `As a <persona>, I want to <action>, so that <outcome>.`
  - `**Acceptance criteria:**` — bulleted list, each as a testable
    condition (`Given / When / Then` is fine but not required if it
    feels heavy)
  - `**Out of scope:**` — what this story explicitly does NOT cover
- `## Edge Cases / Open Questions` — things that aren't acceptance
  criteria but eng will hit. Examples: empty state, error state,
  permissions, multi-device, rate limits
- `## Notes` — anything else: dependencies, related stories, designs

Do NOT paste the document body into chat — the user reads it in the
document pane.

### Depth guardrails

Bad user stories cause rework; good ones unblock eng. Hold yourself to:

- **Persona has a job, not just a label.** "As a user" is filler. "As
  a returning customer who placed 3+ orders in the past year and
  expects to find past invoices" is a story you can build for. Memory
  is your friend here.
- **The "I want" is something the user does, not something you build.**
  Bad: "As an Account Administrator, I want a resilient background
  execution engine that evaluates delivery windows hourly." No admin
  wants a cron dispatcher — that's a technical task in story costume.
  Good: "As an account admin, I want my digest to arrive at the hour
  I chose." Engine work goes in `## Notes` as a dependency.
- **Outcome is the user's, not yours.** "So that we increase retention"
  is a business outcome — it doesn't go in the story. "So that they
  can reorder without re-typing their card details" does.
- **Acceptance criteria are testable.** Each criterion either passes
  or fails in QA. "Performance is fast" is not testable; "Order list
  loads in <500ms p95 with up to 100 orders" is.
- **Specific, but never invented.** If a criterion needs a threshold
  you don't have (latency, volume, order counts), either ask or write
  it as `<threshold — confirm with eng>` under Edge Cases / Open
  Questions. A fabricated "500ms p95" that eng builds to is worse than
  an honest placeholder.
- **At least one edge case.** Empty state, permissioning, error path,
  or partial data — every real feature has one. If you can't name an
  edge case, you haven't thought about the story enough.
- **Keep scope honest.** If the problem is bigger than one story, say
  so and suggest a split. Don't cram a quarter of work into one story
  to feel done.

## Phase 3: Review

After writing, run a scope completeness check: every capability named
in the confirmed intake (e.g. each delivery channel, each user action)
maps to a story or an explicit out-of-scope line. Anything missing —
fix the draft via `EditDocument` before proceeding.

Then call `AwaitReview` with:
- `deliverable_kind: "user_story"`
- `document_id: <slug>`
- `summary_for_user: <one line: persona + outcome>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
