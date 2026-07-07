---
name: quarterly-review
description: Run a quarterly review spanning multiple sprints — what shipped vs. what we said, themes, narrative for stakeholders.
slash_command: quarterly-review
trigger_keywords: ["quarterly review", "quarterly retro", "quarter review", "qbr", "retro for the quarter"]
required_tools: ["RecallMemory", "SearchMemories", "ReadDocument", "ListDocuments", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory"]
phases: ["intake", "drafting", "review"]
---

# Quarterly-Review Workflow

You are running a quarterly review — a retrospective across multiple
sprints, framed as a narrative the user can share with stakeholders or
their team. This is bigger than `/sprint-review` and operates at the
goal/OKR level rather than the chunk level.

## Phase 1: Intake

Before asking anything, pull memory: `RecallMemory` with
`type=product` (goals, targets, and sprint-level state across the
quarter), `type=decision` (decisions that shaped the quarter), and
`type=lessons` (recurring patterns). Query with the quarter label
(e.g. "Q2 2026"), then with product/feature names it surfaces.
RecallMemory has no date filter — the query is a plain text match, so
a date range like "Apr-Jun 2026" as a query will match nothing. Use
what you find to pre-answer the questions below: confirm ("Memory says
you committed to A, B, C in April — still the right list?") instead of
asking cold.

Then ask one at a time, skipping anything already supplied or
answered by memory:

1. **Which quarter?** "Q2 2026", "Apr-Jun 2026", or a date range. Be
   explicit.
2. **What was committed at the start of the quarter?** OKRs, themes,
   roadmap items, or "we said we'd ship A, B, C." If they don't
   remember, ask if they wrote it down anywhere — the `type=product`
   pull above may already have it.
3. **Audience for this review.** Themself / their team / leadership /
   board / customer-facing? Each gets a different framing.
4. **What's the one-line narrative they'd lead with?** Not what
   shipped — the *story*. ("We shipped fewer features but went deeper"
   or "We pivoted from A to B mid-quarter and that's why X slipped.")
   If they don't have one, the review will help them find it.

If past sprint-review docs exist, optionally call `ListDocuments` to
find them, then `ReadDocument` on 2-3 to ground the narrative in
specifics. Don't read more than ~3 — the goal is themes, not transcript.

If memory returns nothing relevant and no sprint-review docs exist,
say so plainly and ask the user to paste whatever they have — a list
of what shipped, a planning doc, even bullet fragments. Every line in
"Goals We Set" and "What We Shipped" must come from the user, memory,
or a document.

If the user answers in one line or says "just draft it", proceed with
what you have: draft from memory + documents, mark unknowns inline as
`[unknown — fill in]`, and list the gaps in the AwaitReview summary
instead of re-interrogating.

## Phase 2: Drafting

Adapt to the audience from intake: **leadership/board** — lead with
outcomes vs. targets, keep Themes to the 2-3 with business impact,
move Memory Updates to the very end (it's for the user, not the
audience); **their team** — keep all sections and name individual
wins; **themself** — the bluntest version, keep every theme and lesson.

Call `WriteDocument` with `title` like "Quarterly Review: <quarter>"
and `content_markdown`:

- `# <Title>`
- `## Headline` — one or two sentences. The narrative the user wants
  the audience to walk away with
- `## Goals We Set` — what was committed at the start. Bullets. Honest
  list (not retconned)
- `## What We Shipped` — bullets, grouped by theme or OKR. Each item
  one line; reference the sprint-review docs for detail
- `## Outcomes & Metrics` — targets vs. actuals for the quarter's goal
  metrics (e.g. "Q2 target: 5,000 weekly active teams — landed 4,200,
  +31% QoQ"). Pull targets from `type=product` memory; ask the user
  for actuals if unknown. If no quantitative targets were set, write
  that plainly — it's a finding, name it in Themes
- `## Goals vs. Reality` — for each committed goal, one line: shipped /
  shipped-and-changed-shape / partial / dropped — and the *why*
- `## Themes` — 3-5 patterns across the quarter. Each is a paragraph.
  These are the durable lessons that should outlive this quarter
- `## Surprises` — what changed mid-quarter that wasn't in the plan
  (good or bad)
- `## What's Next` — the through-line into next quarter. 2-4 bullets,
  not a roadmap dump
- `## Memory Updates` — `type=lessons` and `type=product` entries the
  user should add (with suggested wording)

### Depth guardrails

A quarterly review fails when it's a feature dump. The artifact is the
narrative. Hold yourself to:

- **Goals We Set is honest in both directions.** It contains exactly
  the goals from the planning source — no more, no less. If the user
  committed to X and X didn't happen, X stays on the list with the
  reason next to it. Never add a goal that was never committed;
  something cut mid-quarter that was never a goal belongs in
  Surprises, not in Goals.
- **Shipping is not the outcome.** Every goal marked "shipped" should
  say what happened after — adoption, metric movement, or "too early
  to tell (measuring by <date>)". A quarterly review with zero numbers
  is a story, not a review.
- **Call flat or missed headline metrics plainly.** When a target
  existed, state actual vs. target in one sentence ("Target: $5.0M
  ARR; ended at $4.2M — flat for the quarter"). Never let upbeat
  framing bury the subtraction an exec will do immediately.
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
  that we know X, next quarter we're going to do Y to test Z." If the
  user wants a full roadmap reprioritization, point them at
  `/roadmap-update` as a follow-up — don't fold it in here.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "quarterly_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: quarter + headline narrative>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the doc's Memory Updates entries via
`SaveMemory` (one call per entry, using the suggested wording), then
the skill completes.
