---
name: competitive-analysis
description: Research a competitor or feature area and produce a structured brief — positioning, differentiators, gaps, suggested response.
slash_command: competitive-analysis
trigger_keywords: ["competitive analysis", "competitor analysis", "competitive brief", "analyze competitor", "research competitor"]
required_tools: ["RecallMemory", "SearchMemories", "WebSearch", "WebFetch", "WriteDocument", "AwaitReview"]
phases: ["intake", "research", "review"]
---

# Competitive-Analysis Workflow

You are producing a structured competitive brief — either on one
competitor (deep-dive) or on a feature area across multiple competitors
(landscape). The output is a markdown doc the user can use to inform
strategy or product decisions.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

1. **Subject.** A specific competitor (e.g. "Linear") or a feature area
   across multiple (e.g. "AI in PM tools")? Get a name or a topic.
2. **Decision being informed.** Why are we doing this? Pricing call,
   feature build/buy, positioning refresh, sales objection handling,
   investor narrative? The decision shapes which sections matter most.
3. **Our context.** What's our product / our positioning today, in one
   sentence? If they don't say, pull `type=product` from memory.
4. **Known prior context.** Has the user already researched this? Are
   there specific angles they've heard about (e.g., "I've heard their
   pricing is opaque")? Capture as starting hypotheses to verify.

Pull `type=product` (our positioning), `type=decision` (any past
decision about this competitor or area), and `type=lessons` (anything
prior research taught us).

## Phase 2: Research + Drafting

This phase combines targeted web research and synthesis. Don't spiral —
one focused research pass, then write.

**Research pass.** Use `WebSearch` and `WebFetch` to confirm/contradict
the user's hypotheses and fill obvious gaps. Aim for ~3-6 fetches:
landing page, pricing page, recent product blog post, one independent
review or comparison, one customer-quote source. Stop when you have
enough to write — not when you've read everything.

Call `WriteDocument` with `title` like "Competitive Brief: <subject>"
and `content_markdown`:

- `# <Title>`
- `## Decision Context` — one sentence. What this brief is informing.
- `## Subject Snapshot` — 3-5 sentences on what they are, who they
  serve, where they win
- `## Positioning` — how they frame themselves vs. how the market sees
  them. Pull from their site + one independent source
- `## Strengths` — 3-5 specific capabilities or attributes, each with
  a concrete example or citation
- `## Weaknesses / Gaps` — same shape; honest, not strawman
- `## Differentiators vs. Us` — the deltas that matter for our decision.
  Two columns or paired bullets
- `## Suggested Response` — 2-4 specific moves we should consider, each
  tied to the decision context. Includes a recommendation
- `## Sources` — list of URLs you fetched, plus the date

### Depth guardrails

A competitive brief that just describes the competitor is a Wikipedia
entry; a useful brief moves us toward a decision. Hold yourself to:

- **Strengths and Weaknesses cite something.** "Great UX" is filler;
  "Linear's command palette (Cmd+K) opens to a context-aware action
  list — example flows: assign issue, change status, create sub-issue.
  Source: their docs page X" is a strength. If you can't cite, cut it.
- **Positioning has two views.** What they say about themselves AND
  what an independent source (review, comparison, customer) says. If
  they match, note it. If they don't, that gap is itself signal.
- **Differentiators vs. Us are real, not flattering.** If they're better
  at something, say so. Sycophantic briefs lose to ones that admit gaps.
- **Suggested Response is tied to the decision context.** If this is
  for pricing, the response is about pricing. If it's for build/buy, the
  response weighs both. A generic "we should differentiate on X" with no
  link to the decision is filler.
- **Sources are dated.** Web pages change. A brief that cites a 2-year-old
  pricing page is misleading.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "competitive_brief"`
- `document_id: <slug>`
- `summary_for_user: <one line: subject + the one move you'd recommend>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
