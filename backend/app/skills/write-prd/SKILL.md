---
name: write-prd
description: Guided Product Requirements Document authoring workflow.
slash_command: write-prd
trigger_keywords: ["write a prd", "draft a prd", "create a prd", "write the prd", "write a spec", "draft a spec", "create a spec", "product requirements doc", "product requirements document"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "WebSearch", "WebFetch"]
phases: ["intake", "drafting", "review"]
---

# Write-PRD Workflow

You are walking the user through a structured PRD (Product Requirements
Document) authoring workflow. Follow the phases in order. Do NOT jump
ahead. Do NOT produce the final draft until Phase 2.

## Phase 1: Intake

Your goal in this phase is to gather enough context to write a useful PRD.

**Before asking anything**, call `RecallMemory` with `type=product` and
`SearchMemories` with the user's topic as the query. If memory already
answers an intake question (e.g., the target segment or the team's
north-star metric), don't ask it — confirm it instead: "Memory says the
Q2 activation target is 40% — is that still the success metric here?"

Then ask the user about the following. Ask one at a time while 3+ answers
are missing; once only 1-2 remain, ask them together in a single short
message. Intake should rarely take more than 2-3 exchanges.

1. **Problem statement.** What user problem or opportunity is this PRD for?
2. **Target user.** Who has this problem? What segment/persona?
3. **Success metric.** How will we know this worked? A complete metric
   has four parts: baseline (where it is today), target, timeframe, and
   where it's measured (dashboard/source). If the user can't supply the
   baseline or source, keep the target anyway and add the missing piece
   to Open Questions — do not silently drop it.
4. **Constraints or scope boundaries.** Deadline, team size, tech
   constraints, anything out of scope?

If the user already supplied some of these in their opening message,
acknowledge what you have and ask only for what's missing.

After each answer, briefly reflect back what you heard ("Got it — the
problem is X, the target is Y…") so the user can correct any misreads.

If the user gives one-line answers, declines a question, or says "just
draft it" / "use your judgment": stop asking immediately, make reasonable
assumptions, list every one under `## Assumptions`, and proceed to Phase 2.

When intake is done, call `RecallMemory` with `type=decision` to pull any
context that might affect scope. If the project has existing stakeholder
memories (VPs, eng leads), call `RecallMemory` with `type=stakeholder` too.

Also pull `type=lessons` with the topic as a query — if there's a past
launch in this area that taught a lesson, bake the takeaway into the
PRD's Open Questions or Risks. And call `type=reference` if the PRD
should link out to a dashboard, OKR doc, or design system.

**Do NOT call `WriteDocument` in this phase.**

## Phase 2: Drafting

Only enter this phase after you've completed Phase 1 intake.

1. Call `ListDocuments` first. If a PRD on this same feature already
   exists, tell the user and ask whether to update it (`ReadDocument` +
   `EditDocument`) or start fresh — don't silently create a near-duplicate.

2. If the PRD would benefit from web research (competitor behavior,
   industry norms), call `WebSearch` + `WebFetch` now — one research
   pass is enough, don't spiral.

3. Then call `WriteDocument` with a `title` derived from the problem (e.g.
   "PRD: Two-Factor Auth for Login") and `content_markdown` structured as:

   - `# <Title>`
   - `## Problem` — the problem statement in 2-3 sentences, including why now
   - `## Target Users` — who, with specifics
   - `## Proposed Solution` — the approach at a high level, with the
     tradeoff made explicit
   - `## Requirements` — 3-8 user stories with testable acceptance
     criteria in the form "User can [action] and sees [result]" — never
     "the feature should work well"
   - `## Success Metrics` — measurable outcomes; each needs baseline,
     target, timeframe, and measurement source (route missing parts to
     Open Questions)
   - `## Scope` — In / Out bullets
   - `## Assumptions` — every guess you made because the user didn't
     say; each one something the user can strike
   - `## Dependencies & Timeline` — teams, systems, or decisions this
     waits on, plus target milestones if the user gave a deadline; write
     "No deadline given" rather than inventing one
   - `## Open Questions` — things you weren't sure about; tag them clearly
   - `## Decisions / References` — link to memories you pulled (if any)

4. After writing, briefly tell the user in plain English: "I've drafted
   the PRD. Here are the key choices I made: [1-3 bullets]. Open
   questions I flagged: [list]." Never paste the full PRD into chat —
   the saved document is the deliverable.

### Depth guardrails (apply to every section of the PRD)

A structurally-correct PRD with empty sections is worse than one slightly
messy section with real content. But none of these guardrails license
inventing a name, number, or estimate — the figures in the examples below
show format only, never values to reuse. When drafting, hold yourself to:

- **3-5 substantive sentences minimum per `##` section.** Two-sentence
  sections are a red flag — expand with specifics or cut the section.
- **Name things.** Use real stakeholder names from memory, cite actual
  teams, reference specific decisions or metrics you've pulled. "Engineering
  will build it" is filler; "Platform team (Priya) will own the migration,
  blocked until auth rollout finishes in Q3" is content.
- **Concrete numbers over adjectives.** "Significant user impact" means
  nothing; "affects ~40% of logged-in traffic per last week's usage memo"
  does. If you don't have the number, flag it in Open Questions instead
  of burying an adjective.
- **Explicit tradeoffs in Proposed Solution.** State what you're choosing
  AND what you're giving up. "Option A (build in-house) trades 4 weeks of
  eng time for full control; Option B (vendor) ships in 1 week but locks
  us in. Recommending A because control matters more than speed here."
  Effort estimates come from the user or memory — otherwise leave them
  out and note the gap.
- **Name at least one risk or dependency** in Scope or Open Questions,
  even if the project feels obvious. Nothing is truly unambiguous to the
  team reading this cold.

## Phase 3: Review

Immediately after Phase 2, call `AwaitReview` with:
- `deliverable_kind: "prd"`
- `document_id: <the slug returned by WriteDocument>`
- `summary_for_user: <one-line recap of what the PRD covers>`

**STOP after calling AwaitReview. Do NOT produce any further text in this
turn.** The system takes over and asks the user to approve, revise, or
restart.

If the user replies "revise" with specific feedback, use `EditDocument`
to apply the change, then call `AwaitReview` again with the same slug.
If they say "approve" / "looks good", the skill is complete and you
return to normal conversation.
