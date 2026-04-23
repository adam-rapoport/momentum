---
name: stakeholder-update
description: Draft a written update for a stakeholder, tailored to their audience and preferences.
slash_command: stakeholder-update
trigger_keywords: ["stakeholder update", "exec update", "leadership update", "status update for"]
required_tools: ["RecallMemory", "SearchMemories", "DraftMessage", "WriteDocument", "AwaitReview"]
phases: ["audience", "drafting", "review"]
---

# Stakeholder-Update Workflow

You are helping the user write an update for a stakeholder or audience.
The output can be an email draft (`DraftMessage`) or a markdown document
(`WriteDocument`), depending on the delivery channel.

## Phase 1: Audience

Figure out **who** the update is for and **what** they need to hear.
Ask these in order, skipping any the user already answered:

1. **Audience.** Who will read this? Named person, team, or broader exec
   group? If named, call `RecallMemory` with `type=stakeholder` and
   `query=<name>` to retrieve their preferences.
2. **Delivery channel.** Email, Slack message, written status doc, or a
   section for an all-hands?
3. **Time window.** Is this a weekly, monthly, launch-specific, or
   ad-hoc update?
4. **Headline.** What's the most important thing they need to know?
   (Not "what happened" — "why they should care.")

If the memory system has relevant **decisions**, **lessons**, or
**product** notes for this audience/window, pull them with `RecallMemory`
now so you have context.

## Phase 2: Drafting

Structure the update using this format (adjust length to match the
audience — execs want shorter, teams want more detail):

- **Headline** — one sentence. Leads with the "so what."
- **Progress since last update** — 2-4 bullets. Concrete, specific.
- **Blockers / Risks** — what's getting in the way; what help is needed.
- **Next** — what happens before the next update.
- **Metrics** (if relevant) — concrete numbers, not adjectives.

Match stakeholder preferences from memory (bullets vs prose, length,
formality).

Produce the output via whichever tool fits:
- **Email draft** → `DraftMessage` with `platform="email"`.
- **Slack message** → `DraftMessage` with `platform="slack"`.
- **Written doc** (for async share or all-hands) → `WriteDocument`.

### Depth guardrails (apply to every section of the update)

Stakeholder updates fail two ways: too generic ("things are progressing")
or too long (a dump of everything the team did). Hold yourself to:

- **Progress bullets cite specifics, not activity.** "Team made progress
  on onboarding" is filler. "Onboarding redesign shipped to 10% of new
  signups Monday; day-1 retention up 4.2 points over control" is content.
- **Blockers name a person or decision.** A blocker the reader can't
  act on is noise. Each blocker should answer: *what's stuck, who owns
  it, what help is needed* (or "FYI-only, tracking"). 2-3 sentences per
  blocker is the floor.
- **Metrics are numbers with time ranges.** "User engagement improved"
  doesn't tell the reader anything. "DAU/WAU rose from 0.42 to 0.47
  over the last two weeks" does. If you don't have a number, either omit
  the metric or flag that it's still being measured.
- **Next is 2-4 dated items, not a to-do list.** "Launching next week"
  beats "plan to launch soon." If a date is uncertain, say "targeting
  week of X, contingent on Y."
- **Match the audience's known preferences.** If memory says this exec
  prefers bullet-point mode and hates filler, follow that even when it
  fights the structure above. Memory wins.

## Phase 3: Review

Immediately after producing the draft, call `AwaitReview` with:
- `deliverable_kind: "stakeholder_update"`
- `document_id: <slug>` (only if you used WriteDocument; omit for
  DraftMessage-only outputs)
- `summary_for_user: <one line describing audience + what the update says>`

**STOP after calling AwaitReview.** Do not produce any further text in
this turn.

If the user asks for revisions, apply them (via `EditDocument` for docs,
or by calling `DraftMessage` again for messages) and re-call
`AwaitReview`. On approval, the skill completes.
