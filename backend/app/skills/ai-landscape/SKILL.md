---
name: ai-landscape
description: Write an AI-landscape brief scoped to what external AI shifts mean for THIS company — anchored in the company's own AI bets, with every external claim dated, sourced, and flagged to verify.
slash_command: ai-landscape
trigger_keywords: ["ai landscape brief", "ai landscape memo", "ai trends brief", "scan the ai landscape"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WebSearch", "WebFetch", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# AI-Landscape Workflow

You are writing an AI-landscape brief. The trap in this genre is that
it's about the outside world, which invites confident, unsourced
claims — exactly the fabrication this workflow forbids. So the brief is
scoped deliberately: it reads external AI shifts THROUGH the lens of
this company's own AI bets. The grounded spine — our position, and what
each shift means for US — is the deliverable; external developments are
dated, sourced pointers, never settled facts. A generic AI think-piece
that could describe any company is off-target by construction.

## Phase 1: Intake

FIRST, before asking anything (if the scope wasn't supplied — which
bets or which reader — ask that one question, then):

1. Call `TimeCheck` — external claims are as-of a date; the brief
   states it up front.
2. Call `RecallMemory` with the company's AI work as the query, once
   each for `type=decision` (the AI bets already placed — build-vs-buy,
   in-house, pricing posture — the anchor the whole brief hangs on),
   `type=product` (the AI features shipped/shipping and their quality
   bar), `type=team` (who owns AI/model quality), and `type=lessons`
   (what the company has already learned building AI). If a typed pull
   returns nothing, try one broader `SearchMemories` query, then move
   on — do not stall.
3. Read the PRIMARY sources in full: the strategy memo (the AI bets in
   context) and the decision log (the build-in-house / pricing
   decisions). Uploaded files live as reference memories; `ListDocuments`
   mostly shows generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here are our AI bets I'll
   anchor the brief on — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the company's AI bets you'll anchor on (with sources), the reader and
what decision the brief should inform, and the external areas you'll
scan — and end your turn so the user can steer before you draft.

First message:
1. **Which of our bets is this brief in service of?** In-house models,
   the eval program, the cost posture, a new AI feature — the anchor.
2. **Who's it for, and what should it help them decide?** A board
   update, an eng planning input, a strategy check — sets the altitude.

Second message — one compact checklist:
3. **Which external areas matter?** Model capability, pricing/cost,
   regulation, competitor moves — where to point the scan.
4. **Any external sources you already trust?** Links or reports to
   start from, so the scan isn't cold.

Then run ONE external research pass: `WebSearch` + `WebFetch` on the
areas above. Fetch before you cite. If a search returns nothing usable,
note that — do not fall back on what you "know" about AI (your training
cutoff makes that stale by construction).

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "AI Landscape Brief: <scope>
(<date>)" and `content_markdown` structured as:

- `# <Title>`
- `## Scope & Framing` — one paragraph: this brief reads external AI
  shifts through <company>'s own AI bets; external claims are dated and
  flagged for verification, not treated as settled fact. State the
  as-of date.
- `## Our AI Position Today` — the grounded core: the company's AI
  bets, decisions, and posture from sources (the in-house build, the
  eval gate, the pricing/cost stance), each cited. Everything after
  this hangs off these facts.
- `## External Shifts (as of <date> — verify before citing)` — 3-5
  relevant external developments from the research pass, each with its
  source link, its date, and the explicit "as of <date> — verify"
  flag. No trend appears without a fetched source. If the pass came
  back thin, say exactly that here and keep this section short and
  honest rather than padding it.
- `## So What For Us` — the analytical spine, fully grounded: for each
  external shift, what it means for OUR bets — does it validate the
  in-house build, pressure the cost posture, open a capability we lack,
  or threaten a differentiator? Every "so what" ties to a sourced
  company fact. This section is the point of the brief.
- `## Watch List & No-Regret Moves` — what to monitor, and any
  low-regret actions that follow, each tied to a company fact — not
  generic advice.
- `## Open Questions` — what the scan couldn't settle.
- `## Memory Updates` — propose a `type=reference` entry for external
  sources worth tracking (with their dates). Do NOT write any external
  claim into memory as fact — it's dated and unverified by nature.
  Proposals until saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **External claims are dated, sourced, and flagged — never asserted.**
  Every external development carries its source, its date, and "as of
  <date> — verify before citing". An unfetched trend is not a claim.
  If `WebSearch`/`WebFetch` return nothing usable, say so plainly — an
  honest thin section beats a confident fabricated one.
- **The analysis is grounded in the company's own facts.** Every "so
  what for us" traces to a sourced company bet, decision, or metric.
  The brief's whole value is the connection between an external shift
  and a real internal fact — invent either side and it's worthless.
- **No numbers from memory of the field.** Market sizes, adoption
  rates, benchmark scores, "most teams now…" claims appear ONLY from a
  fetched source. Your training data is stale; treat any AI "fact" you
  didn't fetch as unverified and leave it out.
- **Not a generic think-piece.** If a paragraph could appear in any
  company's AI brief, it doesn't belong in this one. Cut anything not
  tied to a specific company bet.
- **Inform the decision, don't make it.** A landscape brief surfaces an
  external shift's implications and the options it opens — it does NOT
  recommend "approve" or "authorize" an internal decision that the
  sources say is still open (a pricing proposal, a model choice). Frame
  a bearing on an open decision as "this strengthens the case for X;
  the call is still <owner>'s to make" — never a "no-regret move: adopt
  X", and never invent the adopted mechanism (a credit-pool size, a
  price). If a move you surface would reverse a logged decision, flag it
  as a decision change, not continuity.
- **One research pass, not a spiral.** Search, fetch, cite — once.
- **One follow-up per thin answer.** If the scope is vague, ask at
  most ONE follow-up, then draft with what you have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "ai_landscape"`
- `document_id: <slug>`
- `summary_for_user: <one line: scope, shift count, the top "so what for us">`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=reference` for external sources to track, with
dates): one short confirmation listing the entries, then save what the
user okays. Then the skill completes.
