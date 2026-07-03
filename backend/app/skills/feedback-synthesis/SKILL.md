---
name: feedback-synthesis
description: Synthesize a pile of user feedback into themes ranked by frequency and impact, with recommendations.
slash_command: feedback-synthesis
trigger_keywords: ["synthesize feedback", "synthesize user feedback", "feedback synthesis", "cluster feedback", "themes from feedback"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "SaveMemory", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Feedback-Synthesis Workflow

You are turning a pile of raw user feedback (interview notes, survey
responses, support tickets, sales calls, app reviews) into structured
themes a PM can act on.

## Phase 1: Intake

**Do NOT call `WriteDocument` in this phase.**

Only two things truly require asking:

1. **The feedback corpus.** Ask the user to paste it or point to where
   it lives. If they reference feedback that isn't pasted ("the
   interview notes from last week"), call `ListDocuments` and
   `ReadDocument` to find it before asking them to paste — it may
   already be saved as a document.
2. **The decision being informed.** Roadmap prioritization?
   Spec-writing? Investor narrative? Steers the recommendations.

Infer source mix, product area/scope, and time window from the corpus
itself where possible, and confirm inferences in a single line ("Looks
like ~30 support tickets about onboarding from June — right?") rather
than asking separate questions. Never ask more than two questions in a
row. Even when everything is inferable, post that one-line confirmation
before drafting — don't go silent.

If the user declines the questions or says "just synthesize it",
proceed with what you have: state your assumptions about source mix,
scope, and decision context explicitly in `## Source Summary`, and make
Recommendations correspondingly more cautious. Do not stall waiting
for answers.

With `RecallMemory`, pull `type=product` (the area being analyzed —
what's shipped, what's planned) and `type=decision` (recent
prioritization decisions this feedback might confirm or contradict),
plus `type=lessons` in case prior feedback rounds taught something
about the user base. If the type-filtered pulls return nothing, try
`SearchMemories` with the product-area keywords; if that's also empty,
proceed without — don't ask the user to supply strategy context.

## Phase 2: Drafting

**Read the whole corpus end-to-end before counting anything.** If it
lives in a document, `ReadDocument` it in full — never reconstruct it
by paginating through search snippets. State the corpus size only
after you have counted the entries yourself. Before writing any
per-theme frequency, enumerate which entries (by date or ID) belong to
that theme — a count you can't enumerate doesn't go in the doc.
Verification has a budget: ONE full-read attempt. If the corpus is not
fully readable (only fragments or search snippets are retrievable),
stop counting — don't keep probing, and don't guess. Report scope
qualitatively instead ("~3 months of support entries, Apr–Jun; exact
count unavailable — source only partially retrievable"), rank themes
by severity/impact and note the limitation in Caveats. An unverifiable
count never blocks the synthesis: draft with what you have.

Cluster the feedback into themes. A theme is a recurring
job-to-be-done, pain point, or unmet expectation — not just a topic
tag. Aim for 4-8 themes on a corpus of 15+ items; for smaller corpora,
2-4 is right. A theme needs at least 2 independent data points — a
single striking comment is an outlier, not a theme; put it in Caveats
as "worth watching". Never present more themes than the data supports.

Call `WriteDocument` with `title` like "Feedback Synthesis: <area> —
<date range>" and `content_markdown`:

- `# <Title>`
- `## Source Summary` — what was analyzed (count + mix), the decision
  context, and any assumptions you inferred
- `## Headline Findings` — 2-3 sentences on the biggest takeaway
- `## Tensions with Current Plan` — where the feedback confirms or
  contradicts recent decisions or roadmap priorities (use the
  `type=decision` and `type=product` memories you recalled; name the
  decision and date). Omit this section if memory returned nothing
  relevant.
- `## Themes` — ordered by frequency × severity, biggest first (not
  the order you read them). State the ranking criterion in one
  sentence, especially if the order differs from raw frequency. For
  each theme:
  - `### <Theme name>` (specific, not "Performance issues")
  - One paragraph describing the theme
  - **Frequency:** count or % of corpus
  - **Impact:** who's affected, how badly
  - **Representative quote(s):** 1-2 verbatim, with attribution if known
- `## Recommendations` — 3-5 actions, prioritized. Each names what to
  do and which theme(s) support it. Recommendations the synthesis
  doesn't support belong in a separate "Open Questions" section.
- `## Caveats` — sample bias, missing voices, outliers worth watching,
  anything that could make these findings misleading

### Depth guardrails

A synthesis that just summarizes feedback isn't useful — the value is
in the prioritization and the call-to-action. Hold yourself to:

- **Summary-only input gets no quotes.** If the user only described the
  corpus ("20 interviews about onboarding") without raw text, write
  "No verbatim quotes available — summary-only input" under the theme
  instead of producing a quote, and label frequencies "user-reported".
  A fabricated quote is worse than no synthesis.
- **Themes are about jobs/pains, not topics.** "Mobile experience" is
  a topic; "Users abandon checkout on mobile because the keyboard
  covers the price total" is a theme. The first won't help anyone act.
- **Frequency is a number, not a hedge.** Say "12 of 20 interviews
  raised this unprompted" — not "many users mentioned." If you can't
  count, say so.
- **Name the bias.** If the corpus is all power-users, all enterprise,
  all English-speaking, all from one channel — say it. The credibility
  of the synthesis depends on this.

The synthesis lives in the document — do not reproduce it in chat
before or after writing it; the chat gets only the one-line summary
via `AwaitReview`.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "feedback_synthesis"`
- `document_id: <slug>`
- `summary_for_user: <one line: corpus size, top theme, top recommendation>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the headline finding as a `product` memory
and a `reference` memory pointing to the document via `SaveMemory`
(don't save the doc's full content). Then the skill completes.
