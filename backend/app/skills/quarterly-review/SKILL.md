---
name: quarterly-review
description: Run a quarterly review spanning multiple sprints — what shipped vs. what we said, themes, narrative for stakeholders.
slash_command: quarterly-review
trigger_keywords: ["quarterly review", "quarterly retro", "quarter review", "qbr"]
required_tools: ["RecallMemory", "SearchMemories", "ReadDocument", "ListDocuments", "WriteDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Quarterly-Review Workflow

You are running a quarterly review — a retrospective across multiple
sprints, framed as a narrative the user can share with stakeholders or
their team. This is bigger than `/sprint-review` and operates at the
goal/OKR level rather than the chunk level.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

1. **Which quarter?** "Q2 2026", "Apr-Jun 2026", or a date range. Be
   explicit.
2. **What was committed at the start of the quarter?** OKRs, themes,
   roadmap items, or "we said we'd ship A, B, C." If they don't
   remember, ask if they wrote it down anywhere — pull `type=project`
   from memory with the quarter as a query.
3. **Audience for this review.** Themself / their team / leadership /
   board / customer-facing? Each gets a different framing.
4. **What's the one-line narrative they'd lead with?** Not what
   shipped — the *story*. ("We shipped fewer features but went deeper"
   or "We pivoted from A to B mid-quarter and that's why X slipped.")
   If they don't have one, the review will help them find it.

Pull memory broadly: `type=project` (sprint-level state across the
quarter), `type=decision` (decisions that shaped the quarter),
`type=lessons` (recurring patterns), `type=product` (features
shipped). Use the quarter date range as the query window.

If past sprint-review docs exist, optionally call `ListDocuments` to
find them, then `ReadDocument` on 2-3 to ground the narrative in
specifics. Don't read more than ~3 — the goal is themes, not transcript.

## Phase 2: Drafting

Call `WriteDocument` with `title` like "Quarterly Review: <quarter>"
and `content_markdown`:

- `# <Title>`
- `## Headline` — one or two sentences. The narrative the user wants
  the audience to walk away with
- `## Goals We Set` — what was committed at the start. Bullets. Honest
  list (not retconned)
- `## What We Shipped` — bullets, grouped by theme or OKR. Each item
  one line; reference the sprint-review docs for detail
- `## Goals vs. Reality` — for each committed goal, one line: shipped /
  shipped-and-changed-shape / partial / dropped — and the *why*
- `## Themes` — 3-5 patterns across the quarter. Each is a paragraph.
  These are the durable lessons that should outlive this quarter
- `## Surprises` — what changed mid-quarter that wasn't in the plan
  (good or bad)
- `## What's Next` — the through-line into next quarter. 2-4 bullets,
  not a roadmap dump
- `## Memory Updates` — `type=lessons` and `type=project` entries the
  user should add (with suggested wording)

### Depth guardrails

A quarterly review fails when it's a feature dump. The artifact is the
narrative. Hold yourself to:

- **Goals We Set is honest, not retconned.** If the user committed to
  X and X didn't happen, X stays on the list — with the reason next to
  it. Quietly removing failed goals is the worst pattern in PM writing.
- **Goals vs. Reality has 4 buckets, not 2.** Shipped / Shipped-but-
  reshaped / Partial / Dropped. The middle two are where the real
  story is — pure binary status loses the nuance.
- **Themes are 4-6 sentences.** Less and they're bullets; more and
  they're sub-essays. Each theme should be re-readable by someone
  who wasn't in the quarter.
- **Surprises explain the cause and the response.** "We had a bug" is
  noise. "Customer X reported a data-loss bug in week 3, we paused
  feature work for 4 days to ship a fix and a regression test, which
  explains the slip on Y" is the actual story.
- **What's Next is a narrative continuation, not a roadmap.** "Now
  that we know X, next quarter we're going to do Y to test Z." Save
  the full roadmap for `/roadmap-update` or wherever else.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "quarterly_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: quarter + headline narrative>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
