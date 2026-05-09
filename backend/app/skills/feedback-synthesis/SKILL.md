---
name: feedback-synthesis
description: Synthesize a pile of user feedback into themes ranked by frequency and impact, with recommendations.
slash_command: feedback-synthesis
trigger_keywords: ["synthesize feedback", "synthesize user feedback", "feedback synthesis", "cluster feedback", "themes from feedback"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Feedback-Synthesis Workflow

You are turning a pile of raw user feedback (interview notes, survey
responses, support tickets, sales calls, app reviews) into structured
themes a PM can act on.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

1. **The feedback corpus.** Ask the user to paste the feedback into the
   chat, or describe where it came from (e.g., "20 interview notes",
   "last month's CSAT comments"). If they haven't provided text, ask
   them to.
2. **Source mix.** Are these all the same source (interviews) or
   mixed (interviews + tickets + sales calls)? Mix matters for weighting.
3. **Product area / scope.** Is this feedback about one feature, the
   whole product, onboarding, pricing, …? Affects how broad the themes
   should be.
4. **Time window.** When was this collected? Is it ongoing or a one-time
   batch?
5. **Decision being informed.** Why are we doing this synthesis? Roadmap
   prioritization? Spec-writing? Investor narrative? Steers what the
   recommendations look like.

Pull `type=product` (the area being analyzed — what's been shipped,
what's planned) and `type=decision` (recent prioritization decisions
that this feedback might confirm or contradict). Pull `type=lessons`
in case prior feedback rounds taught something about the user base.

## Phase 2: Drafting

Cluster the feedback into themes. A theme is a recurring jobs-to-be-done,
pain point, or unmet expectation — not just a topic tag. Aim for 4-8
themes; fewer means you're being too coarse, more means you haven't
clustered enough.

Call `WriteDocument` with `title` like "Feedback Synthesis: <area> —
<date range>" and `content_markdown`:

- `# <Title>`
- `## Source Summary` — what was analyzed (count + mix), what the
  decision context is
- `## Headline Findings` — 2-3 sentences on the biggest takeaway
- `## Themes` — for each theme:
  - `### <Theme name>` (specific, not "Performance issues")
  - One paragraph describing the theme
  - **Frequency:** rough count or % of corpus
  - **Impact:** who's affected, how badly (cite a representative quote)
  - **Representative quote(s):** 1-2 verbatim, with attribution if known
- `## Recommendations` — 3-5 actions, prioritized. Each names what to
  do and why this synthesis supports it
- `## Caveats` — sample bias, missing voices, anything that could make
  these findings misleading

### Depth guardrails

A synthesis that just summarizes feedback isn't useful — the value is
in the prioritization and the call-to-action. Hold yourself to:

- **Themes are about jobs/pains, not topics.** "Mobile experience" is
  a topic; "Users abandon checkout on mobile because the keyboard
  covers the price total" is a theme. The first won't help anyone act.
- **Frequency is a number, not a hedge.** Say "12 of 20 interviews
  raised this unprompted" — not "many users mentioned." If you can't
  count, say so.
- **Quotes are verbatim.** Don't paraphrase into a quote. If a quote is
  clipped, mark it `[…]`.
- **Recommendations are linked to themes.** Each recommendation cites
  which theme(s) it addresses. Recommendations the synthesis doesn't
  support belong in a separate "Open Questions" or "Future Work" section.
- **Name the bias.** If the corpus is all power-users, all enterprise,
  all English-speaking, all from one channel — say it. The credibility
  of the synthesis depends on this.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "feedback_synthesis"`
- `document_id: <slug>`
- `summary_for_user: <one line: corpus size, top theme, top recommendation>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, the skill completes.
