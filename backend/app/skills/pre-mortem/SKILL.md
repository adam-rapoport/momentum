---
name: pre-mortem
description: Run a pre-mortem — assume the launch already failed, surface why, sort the risks into tigers / paper-tigers / elephants, and assign owners and mitigations grounded in the real launch context.
slash_command: pre-mortem
trigger_keywords: ["premortem", "pre-mortem", "pre mortem", "run a premortem", "premortem the launch"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Pre-Mortem Workflow

You are running a pre-mortem: imagine it's after the launch and it
FAILED, then work backwards to why. The deliverable is a markdown risk
doc a team can act on: the failure premise, the risks surfaced, sorted
into **tigers** (real threats worth mitigating now), **paper-tigers**
(feel scary, aren't), and **elephants** (the risks nobody's saying out
loud), each with an owner and a mitigation. A pre-mortem earns its keep
by naming REAL risks grounded in the actual launch — inventing dramatic
failure modes wastes the exercise.

## Phase 1: Intake

FIRST, before asking anything (if the launch/initiative wasn't
supplied, ask that one question, then):

1. Call `TimeCheck` — the "it's <future date>, it failed" premise
   anchors to the real launch timing.
2. Call `RecallMemory` with the launch as the query, once each for
   `type=product` (what's actually launching — scope, dependencies,
   the moving parts that can break), `type=decision` (bets and
   deferrals that shape the risk surface — a deferred integration, a
   build-vs-buy call), `type=stakeholder` (whose buy-in or handoff the
   launch depends on, and known tensions), and `type=lessons` (how
   past launches in this area actually went wrong — the best source of
   real risks). If a typed pull returns nothing, try one broader
   `SearchMemories` query, then move on — do not stall.
3. Read the PRIMARY sources in full: the launch's PRD or plan, the
   roadmap (what's committed around it), and any post-mortem/lessons
   log. Uploaded files live as reference memories; `ListDocuments`
   mostly shows generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's the launch and the
   risk surface I see — correct anything wrong"), then ask ONLY what's
   missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the launch and its date, the moving parts and dependencies you found
(with sources), and any past-launch lessons that apply — and end your
turn so the user can steer before you draft.

First message:
1. **What's launching, and when?** The initiative and its target
   date — the premise's dateline.
2. **What would "failed" mean here?** The outcome that counts as
   failure (missed the metric, a customer blew up, the launch slipped,
   trust broke) — this sets what risks matter.

Second message — one compact checklist:
3. **Who's in the room / on the hook?** The teams and owners the
   launch depends on — the source for real elephants.
4. **Anything you're already worried about?** The user's own gut
   risks seed the list; you'll pressure-test and sort them.

## Phase 2: Drafting

Call `WriteDocument` with a `title` like "Pre-Mortem: <launch>
(<dateline>)" and `content_markdown` structured as:

- `# <Title>`
- `## The Premise` — "It's <future date>. <launch> shipped and it
  failed. Here's why." The date is the sourced launch date (or
  arithmetic on today); if it isn't sourced, write "date TBD".
- `## Risks Surfaced` — the raw list of plausible failure causes, each
  grounded in the real launch context (a dependency, a decision, a
  known weak spot) and tagged with its source, OR labeled "hypothesis"
  if it's speculation. No invented failure stated as likely.
- `## Sorted: Tigers / Paper-Tigers / Elephants` — three groups:
  - **Tigers** — real, high-impact, plausible. The ones to mitigate now.
  - **Paper-tigers** — the risks that feel scary but are low-probability
    or low-impact; each gets the one-line reason it's overrated, so the
    team stops burning worry on it.
  - **Elephants** — the risks nobody's saying out loud: cross-team
    handoffs, stakeholder misalignment, a deferred decision coming due.
    Each grounded in a real tension (a logged decision, a stakeholder's
    known position, a dependency) — never manufactured drama.
- `## Mitigations & Owners` — per tiger (and any elephant worth acting
  on): the mitigation, an owner (a real person from team/stakeholder
  memory, or "owner TBD" — never invent who's accountable), and the
  earliest signal the risk is materializing.
- `## Watch List` — the leading indicators to monitor from now to
  launch, each tied to a risk above.
- `## Open Questions` — risks you couldn't ground or size.
- `## Memory Updates` — propose a `type=lessons` entry for the top
  risks worth carrying into the launch retro; a `type=decision` entry
  only if the team actually decided a mitigation here. Proposals until
  saved in Phase 3 — never mark one "Saved" in the doc.

### Depth guardrails

- **Risks are grounded or labeled hypotheses.** A failure mode tied to
  the real launch (from the PRD, roadmap, decision log, or lessons) is
  stated with its source. A speculative one is labeled "hypothesis" —
  never dress speculation as a likely outcome.
- **The three buckets earn their labels.** A paper-tiger needs the
  one-line reason it's overrated. An elephant needs the real underlying
  tension — a logged decision, a stakeholder concern, a cross-team
  dependency — not invented interpersonal conflict.
- **Elephants come from evidence, not theater.** The unspoken risk is
  grounded in a real deferred decision, dependency, or known
  stakeholder position. Inventing a political conflict to sound
  insightful is fabrication.
- **Owners are real or TBD.** Assign a mitigation to a person only if
  team/stakeholder memory names them for that area; otherwise "owner
  TBD". Don't put a name on a risk to make it look handled.
- **Dates are computed or TBD.** The premise's dateline uses the
  sourced launch date or arithmetic on today. No invented dates.
- **One follow-up per thin answer.** If the launch or the failure bar
  is vague, ask at most ONE follow-up, then draft with what you have,
  marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "pre_mortem"`
- `document_id: <slug>`
- `summary_for_user: <one line: launch, tiger count, the top risk>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (`type=lessons` for the carry-forward risks; `type=decision`
for a mitigation the user actually decided): one short confirmation
listing the entries, then save what the user okays. Then the skill
completes.
