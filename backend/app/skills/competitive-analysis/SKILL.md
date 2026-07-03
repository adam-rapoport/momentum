---
name: competitive-analysis
description: Research a competitor or feature area and produce a structured brief — positioning, differentiators, gaps, suggested response.
slash_command: competitive-analysis
trigger_keywords: ["competitive analysis", "competitor analysis", "competitive brief", "analyze competitor", "research competitor"]
required_tools: ["RecallMemory", "SearchMemories", "WebSearch", "WebFetch", "WriteDocument", "EditDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Competitive-Analysis Workflow

You are producing a structured competitive brief — either on one
competitor (deep-dive) or on a feature area across multiple competitors
(landscape). The output is a markdown doc the user can use to inform
strategy or product decisions.

## Phase 1: Intake

**Step 0 — before asking anything:** call `SearchMemories` with the
competitor/topic name, and `RecallMemory` with `type=product`, then
`type=decision`, then `type=lessons`. Skip any question below that
memory already answers, and surface past decisions or prior research
about this subject as starting hypotheses: "Memory says we decided X
about Linear in Q1 — is that still the frame?"

Then ask one at a time, skipping anything already supplied:

1. **Subject.** A specific competitor (e.g. "Linear") or a feature area
   across multiple (e.g. "AI in PM tools")? Get a name or a topic. If
   the user asks YOU to pick (e.g. "the most dangerous one"), record why
   you picked it in the doc's Decision Context — and if the source doc's
   wording points at a different competitor than your pick, flag that
   ambiguity to the user instead of silently choosing.
2. **Decision being informed.** Pricing call, feature build/buy,
   positioning refresh, sales objection handling, investor narrative?
   The decision shapes which sections matter most. If the user has no
   specific decision ("just keeping an eye on them"), don't push — set
   Decision Context to "general awareness ahead of the next planning
   cycle" and make Suggested Response the 2-3 competitor signals to
   watch that would trigger a real decision (e.g. "if they ship X or
   drop price below Y, revisit").
3. **Our context.** What's our product / our positioning today, in one
   sentence? Skip if Step 0's `type=product` pull already answered it.
4. **Known prior context.** Has the user already researched this? Are
   there specific angles they've heard about (e.g., "I've heard their
   pricing is opaque")? Capture as starting hypotheses to verify.

**Do NOT call `WriteDocument` in this phase.**

## Phase 2: Drafting

This phase combines targeted web research and synthesis. Don't spiral —
one focused research pass, then write.

**Research pass.** Use `WebSearch` and `WebFetch` to confirm/contradict
the starting hypotheses and fill obvious gaps. Aim for ~3-6 fetches:
landing page, pricing page, recent product blog post, one independent
review or comparison, one customer-quote source. Stop when you have
enough to write — not when you've read everything.

Call `WriteDocument` with `title` like "Competitive Brief: <subject>"
and `content_markdown`:

- `# <Title>`
- `## Decision Context` — one sentence. What this brief is informing
  (and, if you picked the subject, why).
- `## Subject Snapshot` — 3-5 sentences on what they are, who they
  serve, where they win
- `## Positioning` — how they frame themselves vs. how the market sees
  them. Pull from their site + one independent source
- `## Pricing & Packaging` — tiers, price points, and packaging model,
  even approximate, with the as-of date. If pricing is not public after
  checking their site, say exactly that — opaque pricing is itself
  signal.
- `## Strengths` — 3-5 specific capabilities or attributes, each with
  a concrete example or citation
- `## Weaknesses / Gaps` — same shape; honest, not strawman
- `## Differentiators vs. Us` — a two-column markdown table — `Them` |
  `Us` — one row per delta that matters for the decision, including
  rows where they win
- `## Suggested Response` — 2-4 specific moves we should consider, each
  tied to the decision context. Includes a recommendation
- `## What We Couldn't Verify` — 2-4 bullets: starting hypotheses left
  unconfirmed, data you looked for and didn't find, and any claim
  resting on a single source. Absence of data is information; this
  section is what stops the brief from overclaiming.
- `## Sources` — every URL you fetched, each with its date, plus any
  internal docs/memories used. Always record the web-check outcome:
  if searches came up dry, "no relevant public updates found
  (searched <date>)" is a valid, required entry.

**If the subject is a feature area across multiple competitors
(landscape mode),** replace `Subject Snapshot` / `Strengths` /
`Weaknesses / Gaps` with:

- `## Comparison Table` — a markdown table, one row per competitor,
  columns = the 3-5 dimensions that matter for the decision (always
  include Pricing if findable); mark each cell as confirmed (cite the
  source) or inferred (add "?")
- `## Per-Competitor Notes` — 2-4 bullets each: where they win, where
  they're weak, one citation each

Keep `Decision Context`, `Differentiators vs. Us`, `Suggested Response`,
`What We Couldn't Verify`, and `Sources` in both modes.

### Depth guardrails

A competitive brief that just describes the competitor is a Wikipedia
entry; a useful brief moves us toward a decision. Hold yourself to:

- **Strengths and Weaknesses cite something.** "Great UX" is filler.
  If you can't cite, cut it — and the citation must be REAL: a quote
  goes in verbatim from its source or not at all, and any competitor
  capability claim needs a page you fetched this session or a named
  internal doc/memory. An invented citation with a plausible date is
  worse than no claim.
- **If a search or fetch fails** (the tool returns an Error) or a page
  has nothing useful, say so in your notes and move on — never invent a
  citation or cite a page you didn't fetch. If you finish the research
  pass with fewer than 2 usable sources, STOP: tell the user what you
  couldn't retrieve and ask whether to (a) write a clearly-caveated
  brief from what you have, or (b) narrow the subject.
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
- `document_id: <the slug returned by WriteDocument>`
- `summary_for_user: <one line: subject + the one move you'd recommend>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
