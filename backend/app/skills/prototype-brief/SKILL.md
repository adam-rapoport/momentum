---
name: prototype-brief
description: Turn an idea or PRD into a build-ready prototype package — flows, screens, sample data, and paste-ready generation prompts for a prototyping tool or coding agent.
slash_command: prototype-brief
trigger_keywords: ["prototype brief", "prototyping brief", "prototype prompt", "build prompt", "prompt for lovable", "prompt for v0"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Prototype-Brief Workflow

You are turning an idea (often an existing PRD) into a build-ready
prototype package. The deliverable is a markdown doc whose centerpiece
is one or more paste-ready generation prompts: either for a
prototyping tool (Lovable, v0 — "show me a working demo") or for a
coding agent (Claude Code, Cursor — "implement this for real"). The
brief succeeds when someone can paste the prompt and get the right
thing without asking you anything.

## Phase 1: Intake

FIRST, before asking anything (if the feature/idea wasn't supplied,
ask that one question, then):

1. Call `TimeCheck` — only for dating the doc; prototypes don't need
   schedules.
2. Call `RecallMemory` with the feature as the query, once each for
   `type=product` (what the product does, the feature's intent,
   existing UI patterns) and `type=decision` (scope decisions that
   bound what the prototype may show). If a typed pull returns
   nothing, try one broader `SearchMemories` query, then move on —
   do not stall.
3. Call `ListDocuments` and look for (a) the feature's PRD or spec —
   the single best input — and (b) research or feedback docs that name
   the workflow being prototyped. `ReadDocument` what you find.
4. Present what you found in 2-3 bullets ("Here's what I have on
   <feature> — correct anything wrong"), then ask ONLY what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. If the opening message plus documents cover
everything, go straight to Phase 2.

First message:
1. **Target: demo or real build?** (a) a prototyping tool for a
   clickable demo, or (b) a coding agent implementing production code
   — and which tool, if they know. This decides the prompt's shape.
2. **What must the prototype prove?** The one question it answers
   ("would a PM understand this digest at a glance?") — this bounds
   the scope.

Second message — one compact checklist:
3. **The core flow.** The user path the demo must walk, if no PRD
   covers it.
4. **Fidelity constraints.** Brand/design requirements, or is
   tool-default styling fine?

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Prototype Brief: <feature>"
and `content_markdown` structured as:

- `# <Title>`
- `## Goal` — what the prototype must prove, for whom, and the target
  (demo tool vs coding agent, named).
- `## User Flow` — the numbered happy path, step by step, plus the 1-2
  states that matter most (empty state, error state).
- `## Screens` — per screen: name, purpose, key elements, and state
  variations. 3-5 screens max unless the user asked for more; a demo
  that proves one thing beats a tour.
- `## Sample Data` — the realistic dataset the prototype ships with,
  inline (names, rows, values). Derive it from source documents where
  they exist; anything you make up must be plainly synthetic and
  internally consistent. Never reuse real customer names or figures
  unless a source supplies them.
- `## Generation Prompt` — the paste-ready prompt in ONE fenced block
  (one block per target if the user wants both). It must be fully
  self-contained: restate the flow, screens, sample data, and
  constraints inside the prompt itself.
- `## Out of Scope` — what the prototype deliberately fakes or omits
  (auth, persistence, real integrations), stated so nobody mistakes
  the demo for the product.
- `## Demo Script` — 3-6 steps: what to click and what to look for,
  tied back to the goal.
- `## Memory Updates` — propose a `type=product` entry (the prototype's
  goal + scope decisions it encodes). Proposals until saved in Phase 3
  — never mark one "Saved" in the doc.

### Depth guardrails

- **The generation prompt is self-contained.** The target tool cannot
  see this workspace: never reference "the PRD", "the doc above", or a
  memory inside the prompt — inline everything it needs. If the prompt
  wouldn't work pasted into a fresh tool by a stranger, it's not done.
- **Prototype ≤ PRD.** The prototype may show less than the spec,
  never more: don't add capabilities, screens, or data the source
  doesn't support — a demo that oversells creates a commitment nobody
  made.
- **Sample data is sourced or labeled synthetic.** Real numbers and
  names come verbatim from documents; everything else is invented-by-
  design and must look it (no real-sounding customer names when the
  sources already provide real ones to use).
- **Respect the target's job.** A demo-tool prompt optimizes for
  looking right (screens, sample data, zero setup); a coding-agent
  prompt optimizes for being right (data model, edge cases,
  acceptance criteria). Don't ship one prompt pretending to do both —
  if the user wants both targets, write two prompts.
- **One follow-up per thin answer.** If the flow or goal is vague, ask
  at most ONE follow-up, then draft with what you have, marking
  unknowns in Out of Scope.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "prototype_brief"`
- `document_id: <slug>`
- `summary_for_user: <one line: feature, target tool, screen count>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=product` for the prototype goal + scope): one
short confirmation listing the entries, then save what the user okays.
Then the skill completes.
