---
name: user-story
description: Turn a vague problem statement or feature idea into structured user stories with acceptance criteria and edge cases.
slash_command: user-story
trigger_keywords: ["user story", "user stories", "write a user story", "draft user stories", "as a user"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# User-Story Workflow

You are turning a problem statement or feature idea into one or more
structured user stories that engineering can pick up. Output is a
markdown doc.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

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
5. **Granularity.** Is this one story or several? If the feature is
   big, ask whether to split into multiple stories now or write one
   epic-level story plus a breakdown note.

Pull `type=stakeholder` (if a named persona maps to a known segment)
and `type=product` (existing product context that constrains the story).

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
- `## Problem` — one paragraph. The pain or opportunity.
- `## Persona` — who has this, why they have it, what they'd do today
  to work around it
- `## Story` (or `## Stories` for multiple)
  - `### Story 1: <short title>`
  - `As a <persona>, I want to <action>, so that <outcome>.`
  - `**Acceptance criteria:**` — bulleted list, each as a testable
    condition (`Given / When / Then` is fine but not required if it
    feels heavy)
  - `**Out of scope:**` — what this story explicitly does NOT cover
- `## Edge Cases / Open Questions` — things that aren't acceptance
  criteria but eng will hit. Examples: empty state, error state,
  permissions, multi-device, rate limits
- `## Notes` — anything else: dependencies, related stories, designs

### Depth guardrails

Bad user stories cause rework; good ones unblock eng. Hold yourself to:

- **Persona has a job, not just a label.** "As a user" is filler. "As
  a returning customer who placed 3+ orders in the past year and
  expects to find past invoices" is a story you can build for. Memory
  is your friend here.
- **Outcome is the user's, not yours.** "So that we increase retention"
  is a business outcome — it doesn't go in the story. "So that they
  can reorder without re-typing their card details" does.
- **Acceptance criteria are testable.** Each criterion either passes
  or fails in QA. "Performance is fast" is not testable; "Order list
  loads in <500ms p95 with up to 100 orders" is.
- **At least one edge case.** Empty state, permissioning, error path,
  or partial data — every real feature has one. If you can't name an
  edge case, you haven't thought about the story enough.
- **Keep scope honest.** If the problem is bigger than one story, say
  so and suggest a split. Don't cram a quarter of work into one story
  to feel done.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "user_story"`
- `document_id: <slug>`
- `summary_for_user: <one line: persona + outcome>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
