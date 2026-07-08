---
name: prompt-pack
description: Build a reusable prompt pack for a real team workflow — the workflow's actual steps codified into paste-ready prompts with shared context, sourced examples, and guardrails from the known failure modes.
slash_command: prompt-pack
trigger_keywords: ["prompt pack", "prompt library", "context engineering", "reusable prompts"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Prompt-Pack Workflow

You are building a reusable prompt pack — a set of paste-ready prompts
that codify a REAL team workflow so it runs the same way every time.
The deliverable is a markdown doc the team can use directly: a shared
context block, one prompt per workflow step (each with inputs, output
format, and the must-never rules), and worked examples. The whole value
is that the prompts reflect the team's ACTUAL workflow and its known
failure modes — a pack of generic "summarize this" prompts is worthless.

## Phase 1: Intake

FIRST, before asking anything (if the workflow the pack is for wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — date the pack so its version is trackable.
2. Call `RecallMemory` with the workflow as the query, once each for
   `type=product` (the feature/flow the pack supports — its real steps,
   inputs, and outputs), `type=team` (who runs the workflow and owns
   it), `type=lessons` (the known failure modes the prompts must
   prevent — the richest source of guardrails), and `type=decision`
   (any decision that constrains how the workflow runs — e.g. a
   human-review rule). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Read the PRIMARY sources in full: the PRD/spec for the workflow (its
   real steps), the failure-example log if one exists (the guardrails
   come from here), and any raw material the prompts will operate on
   (the actual feedback/tickets/threads). Uploaded files live as
   reference memories; `ListDocuments` mostly shows generated
   deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the workflow and the
   failure modes I'll build the pack around — correct anything wrong"),
   then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the workflow's real steps (with their source), the failure modes the
prompts will guard against (from the log), and the model/tool the pack
targets if known — and end your turn so the user can steer before you
draft.

First message:
1. **Which workflow, and what are its steps?** The named flow (triage,
   digest-drafting, QA) and the sequence of steps — from a source if
   one exists; this is the pack's skeleton.
2. **Who uses it, and where does it run?** The team and the tool/model
   the prompts paste into — this sets the format.

Second message — one compact checklist:
3. **What must never happen?** The failure modes the prompts must
   prevent (fabricated quotes, wrong attribution) — from the failure
   log if there is one.
4. **What real material can seed examples?** Actual tickets, threads,
   or feedback the prompts operate on — so examples aren't invented.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Prompt Pack: <workflow>" and
`content_markdown` structured as:

- `# <Title>`
- `## Workflow This Codifies` — the real, named workflow and its steps,
  traced to the source, with where each prompt plugs in. If the steps
  aren't clear from sources, say so and ask — don't invent a workflow.
- `## Shared Context Block` — the reusable context every prompt carries:
  the product one-liner, the domain facts, and the guardrails that apply
  pack-wide (e.g. "never put quotation marks around words a customer
  didn't write"). This is the context-engineering backbone; a fenced
  block the team pastes ahead of each prompt.
- `## Prompts` — one subsection per workflow step. Each: **Purpose**
  (one line), **Inputs** (the real fields pasted in), the **Prompt** as
  a fenced block (role, inputs, output format, the must-never rules from
  the failure taxonomy), and an **Example** (a realistic input→output
  using sourced material or a clearly-labeled synthetic placeholder).
- `## Guardrails & Failure Modes` — the known failure modes the pack
  prevents, cited from the logged taxonomy (class + count verbatim), and
  which prompt guards each one.
- `## Usage Notes` — how the team runs the pack, where it lives, who
  owns updates, and how a prompt change gets reviewed.
- `## Open Questions` — steps or guardrails the sources couldn't settle.
- `## Memory Updates` — propose a `type=reference` or `type=product`
  entry recording the pack's existence, scope, and owner. Nothing is
  "decided" beyond what the user confirmed. Proposals until saved in
  Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **The prompts encode the real workflow, not a template.** Every
  prompt maps to an actual step from the sourced workflow. A pack of
  generic prompts that ignores the team's real process is a failed
  deliverable — cut it and ask for the workflow instead.
- **Guardrails come from the logged failure modes.** The must-never
  rules baked into each prompt trace to the real failure taxonomy
  (fabricated quotes, wrong-customer attribution, stale data) — cite
  it with counts, don't invent a generic safety checklist.
- **Examples use sourced material or labeled placeholders.** An
  illustrative input→output uses real feedback/customers from sources,
  or a clearly-marked `[synthetic example]`. Never fabricate a customer
  quote presented as real — that's the exact failure the pack exists to
  prevent, and doing it in the pack itself is disqualifying.
- **A prompt is paste-ready or it's a sketch.** Each fenced prompt has
  role, inputs, output format, and constraints — enough to paste and
  run. A one-line "prompt idea" goes to Open Questions, not the pack.
- **No invented model/tool claims.** If the pack targets a specific
  model or tool, its behavior and limits come from sources or the user;
  don't assert a capability without a source.
- **One follow-up per thin answer.** If the workflow or failure modes
  are vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "prompt_pack"`
- `document_id: <slug>`
- `summary_for_user: <one line: workflow, prompt count, the guardrails baked in>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=reference`/`type=product` for the pack's existence
and owner): one short confirmation listing the entries, then save what
the user okays. Then the skill completes.
