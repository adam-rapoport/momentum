---
name: ai-risk-review
description: Run a pre-launch responsible-AI review for an AI feature — a checklist across accuracy, fabrication, bias, privacy, human oversight, monitoring, failure handling, and disclosure, each item citing the feature's real mechanism or naming the gap.
slash_command: ai-risk-review
trigger_keywords: ["ai risk review", "responsible ai review", "ai risk assessment", "responsible ai checklist"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# AI-Risk-Review Workflow

You are running a pre-launch responsible-AI review for a specific AI
feature. The deliverable is a markdown checklist a launch owner can
sign off against: each risk dimension marked with a real status, backed
by the feature's actual mechanism (cited) or with the gap named
honestly. A safety doc full of green checks and no evidence is worse
than useless — it manufactures false confidence. Every item either
cites how the risk is handled today or says plainly that it isn't.

## Phase 1: Intake

FIRST, before asking anything (if the feature under review wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — a risk review is a point-in-time snapshot; date it.
2. Call `RecallMemory` with the feature as the query, once each for
   `type=product` (what the feature does, its inputs/outputs, the
   quality bar), `type=decision` (safety/quality decisions already made
   — a human-review policy, a blocking rule), `type=team` (who owns
   model quality and who'd own each mitigation), and `type=lessons`
   (the logged failure modes — the real risk surface). If a typed pull
   returns nothing, try one broader `SearchMemories` query, then move
   on — do not stall.
3. Read the PRIMARY sources in full: the feature's PRD/spec (what it
   does and to whom) and the failure-example log / eval doc (the real
   failure taxonomy, the gate, the hold-for-review policy). Uploaded
   files live as reference memories; `ListDocuments` mostly shows
   generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the feature and the
   safety mechanisms on record — correct anything wrong"), then ask
   ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
what the feature does, the failure taxonomy and gate on record (with
sources), and the human-oversight/review policy if one exists — and end
your turn so the user can steer before you draft.

First message:
1. **What's the feature, and who does its output reach?** The AI
   behavior and its audience (customer-facing? internal?) — this sizes
   the blast radius.
2. **What safeguards exist today?** Gates, human review, monitoring —
   from a source if one exists, or "none on record".

Second message — one compact checklist:
3. **Any compliance or data constraints?** PII handling, tenant
   isolation, a security program (SOC 2), disclosure rules.
4. **What's the launch decision, and who signs off?** GA, a wider
   beta, and who owns the go/no-go.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "AI Risk Review: <feature>
(<date>)" and `content_markdown` structured as:

- `# <Title>`
- `## Feature Under Review` — what the feature does, its inputs and
  outputs, who its output reaches, and the primary quality bar (cited).
- `## Risk Checklist` — the core. One row per dimension: **Dimension |
  Status | Evidence or gap**. Status is one of *mitigated / partial /
  gap / unassessed*. Cover at least:
  - **Accuracy / hallucination** — what the model gets wrong; the
    sourced failure taxonomy and the groundedness gate.
  - **Fabrication / quote integrity** — the fabricated-content failure
    class and any hard block on it.
  - **Bias / fairness** — uneven treatment across customers/segments;
    cite a test or mark "unassessed — no bias testing on record".
  - **Privacy / PII / data boundaries** — what the model sees, tenant
    isolation, what it must not see; sourced or flagged.
  - **Human oversight / override** — is there a human in the loop; the
    hold-for-review / approval policy if one exists.
  - **Monitoring / drift** — how failures are caught post-launch;
    trend tracking on record or named as a gap.
  - **Failure handling / fallback** — what the user experiences when
    the model fails (fallback copy, held output, no send).
  - **Disclosure / labeling** — is AI-generated content marked as such;
    any compliance context.
  Each row cites the real mechanism from a source OR names the gap — no
  bare "handled".
- `## Top Risks & Required Actions` — the must-fix-before-launch items,
  each with an owner (real person from memory, or "owner TBD") and the
  action.
- `## Open Questions` — the dimensions you couldn't assess from sources.
- `## Memory Updates` — propose a `type=product` entry for the
  safeguards on record and a `type=decision` entry ONLY for a
  risk-acceptance the user actually made here. Proposals until saved in
  Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Every item cites a mechanism or names the gap.** "Bias: handled" is
  a failed row. Either cite the real safeguard from a source or write
  "unassessed — no bias testing on record" and mean it. Green checks
  without evidence are the failure mode this review exists to catch.
- **Never invent a safeguard.** Claim a control exists — human review,
  PII scrubbing, monitoring, a disclosure label — ONLY if a source
  records it. Inventing a control the team doesn't have is the most
  dangerous fabrication possible in a safety doc; when unsure, it's a
  gap.
- **The failure taxonomy is sourced and counted.** Failure classes and
  their counts come verbatim from the logged examples; the largest
  class and the gate rule anchor the accuracy and fabrication rows.
- **Honest gaps beat false assurance.** An unassessed dimension is
  named as a gap with a proposed next step (a bias audit, a red-team
  pass) — never smoothed over with a confident "no issues".
- **Owners are real or TBD.** Assign a required action to a person only
  if memory names them for that area; otherwise "owner TBD".
- **One follow-up per thin answer.** If the safeguards or the launch
  decision are vague, ask at most ONE follow-up, then draft with what
  you have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "ai_risk_review"`
- `document_id: <slug>`
- `summary_for_user: <one line: feature, dimensions covered, the top must-fix risk>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the safeguards on record; `type=decision`
only for a risk-acceptance the user actually made): one short
confirmation listing the entries, then save what the user okays. Then
the skill completes.
