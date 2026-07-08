---
name: opportunity-assessment
description: Assess a product opportunity and draft the business case — evidence, strategic fit, options with honest costs, and a build / don't-build / learn-more recommendation.
slash_command: opportunity-assessment
trigger_keywords: ["opportunity assessment", "assess the opportunity", "write a business case", "draft a business case", "build a business case"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Opportunity-Assessment Workflow

You are assessing whether an opportunity is worth building. The
deliverable is a markdown business case a decision-maker can say yes
or no to: the evidence for the problem, the strategic fit, the honest
options with their costs, and a clear recommendation — build,
don't-build, or learn-more-first. The document's job is to make the
decision easy to make and hard to regret, not to sell the idea.

## Phase 1: Intake

FIRST, before asking anything (if the opportunity being assessed
wasn't supplied, ask that one question, then):

1. Call `TimeCheck` — decision timelines and evidence freshness
   anchor to today.
2. Call `RecallMemory` with the opportunity as the query, once each
   for `type=product` (what exists today, adjacent bets, metrics the
   opportunity would move), `type=decision` (has this — or something
   overlapping — already been decided, deferred, or declined?),
   `type=stakeholder` (who's asking for it, who decides), and
   `type=lessons` (how similar bets went). If a typed pull returns
   nothing, try one broader `SearchMemories` query, then move on — do
   not stall.
3. Read the PRIMARY sources in full: research notes, win/loss data,
   the roadmap (is this already on it, and where?), and strategy
   docs the case must square with. Uploaded files live as reference
   memories; `ListDocuments` mostly shows generated deliverables —
   treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the evidence I
   have on <opportunity> — correct anything wrong"), then ask ONLY
   what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the evidence you found (with counts and sources), any logged decision
that already touches this opportunity, and the strategy bet it would
serve — and end your turn so the user can steer before you draft.

First message:
1. **What's the opportunity, and what triggered it now?** A customer
   ask, a lost deal, a competitor move, a hunch — the trigger shapes
   the evidence bar.
2. **What decision does this document feed?** Roadmap slot, headcount
   ask, exec pitch — and who makes the call.

Second message — one compact checklist:
3. **Constraints.** Team capacity, budget, or commitments that bound
   the options.
4. **The bar.** What would make this an obvious yes — or an obvious
   no — in the decider's eyes?

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Opportunity Assessment:
<opportunity>" and `content_markdown` structured as:

- `# <Title>`
- `## The Opportunity` — 2-3 sentences: the problem or opening, for
  whom, and the trigger. No adjectives doing evidence's job.
- `## Evidence` — table: **Signal | Source | Strength**. Each signal
  verbatim or counted from a named source (lost-deal counts, quotes,
  usage numbers). Weak evidence is listed as weak — thin evidence
  with honest labels beats padded conviction.
- `## Strategic Fit` — which strategy bet or company goal this
  serves, citing the strategy source; if it serves none, say so
  plainly — that IS the finding.
- `## Sizing` — only what the sources support: affected accounts,
  revenue at stake, request frequency — each with its source and
  arithmetic shown. If the sources can't size it, write "not sizable
  from current sources" and list what data would size it. NEVER
  estimate a market size the sources don't contain.
- `## Options` — 2-4 real options including "do nothing" and, where
  honest, "learn more first" (the cheapest test that would settle
  the biggest unknown). Per option: what it is, effort (only from
  sources or the user, else "effort unestimated"), and the tradeoff.
- `## Risks & Unknowns` — what could make this a regret, including
  any `type=lessons` pattern that applies.
- `## Recommendation` — build / don't-build / learn-more-first, with
  the 2-3 sentence reasoning chain from the evidence. This is a
  recommendation for the user to accept, adjust, or reject — the
  Phase 3 review is where it becomes a decision.
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose a `type=decision` entry (the verdict,
  IF approved) and `type=product` (durable evidence facts worth
  keeping). Proposals until saved in Phase 3 — never mark one
  "Saved" in the doc.

### Depth guardrails

- **Evidence is counted or quoted, never vibed.** "6 of 14 lost
  mid-market deals cited X" is evidence; "customers frequently ask"
  is not, unless a source says it. Every Evidence row names its
  source.
- **No invented sizing.** TAM/SAM figures, revenue projections, and
  adoption estimates appear only when their inputs exist in the
  sources, with the arithmetic shown. An assessment that says "we
  can't size this yet" is complete; one with a made-up market size
  is broken.
- **Honor the decision log.** If `type=decision` memory shows this
  opportunity (or a conflicting bet) was already decided or deferred,
  the assessment says so up front and frames itself as a revisit —
  never as a first look.
- **"Do nothing" is a real option.** Give it the same honest
  treatment: what it costs to not do this, grounded in the evidence
  — not a strawman to make "build" look good.
- **Effort comes from sources or stays unestimated.** Never invent
  an engineering estimate to complete an options table; "effort
  unestimated — needs eng sizing" is the honest cell.
- **The recommendation must be falsifiable.** Name what evidence
  would flip it ("if the next 10 win/loss calls don't mention this,
  downgrade"). A case that can't be wrong isn't a case.
- **One follow-up per thin answer.** If the trigger or the decision
  at stake is vague, ask at most ONE follow-up, then draft with what
  you have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "opportunity_assessment"`
- `document_id: <slug>`
- `summary_for_user: <one line: opportunity, evidence strength, the recommendation>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=decision` for the approved verdict;
`type=product` for durable evidence facts): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
