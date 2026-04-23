---
name: meeting-prep
description: Prepare for a meeting — pull context, draft agenda, flag decisions needed.
slash_command: meeting-prep
trigger_keywords: ["meeting prep", "prep for meeting", "prep for the meeting", "prepare for a meeting", "prepare for my meeting"]
required_tools: ["RecallMemory", "SearchMemories", "WebSearch", "WriteDocument", "AwaitReview"]
phases: ["context", "agenda", "review"]
---

# Meeting-Prep Workflow

You are preparing the user for an upcoming meeting. The deliverable is a
markdown prep doc with attendees, topics, decisions needed, and
pre-reads.

## Phase 1: Context

Ask for what you need, one at a time:

1. **Meeting purpose.** Why are we meeting? (Status review, decision,
   kickoff, retro, 1:1, …)
2. **Attendees.** Who's in the room? For each named person, call
   `RecallMemory` with `type=stakeholder` to surface preferences,
   concerns, or veto power.
3. **Time + format.** How long? In-person, video, hybrid? Pre-read
   culture?
4. **Desired outcomes.** What needs to be true at the end of the
   meeting that isn't true now? (Decisions made, alignment reached,
   unblocked, …)

If the meeting is about a specific topic (a launch, a migration, a
strategy shift), also call `RecallMemory` with `type=product` and
`type=decision` using the topic as the query.

If the meeting topic benefits from external context (competitor move,
industry news, library docs), run a targeted `WebSearch` + `WebFetch`.
One pass only.

## Phase 2: Agenda

Call `WriteDocument` with a `title` like "Meeting Prep: <topic> —
<date>" and `content_markdown` structured as:

- `# <Title>`
- `## Purpose` — one sentence
- `## Attendees` — list with role; note preferences/concerns from memory
- `## Pre-read` — links or context each attendee should have in advance
- `## Agenda` — time-boxed items, each marked `[Decision]`, `[Discussion]`,
  or `[FYI]`
- `## Decisions Needed` — explicit list. Every decision item gets: the
  question, the options, your recommendation
- `## Open Risks / Watchouts` — anything you saw in memory that could
  derail the meeting
- `## Desired Outcome` — the "true at the end" criteria from intake

Keep items time-boxed (e.g., `15m`). Reserve the last 5 minutes for
action items + owners.

### Depth guardrails (apply to every section of the prep doc)

A meeting prep doc is only useful if the reader walks in knowing what
they'd have to dig up themselves. Hold yourself to:

- **Attendees list surfaces something, not just a name.** For each
  person pulled from memory, include one line on their stake, preference,
  or known concern — e.g. "Priya (Platform lead, skeptical of vendor
  dependencies from the OAuth retro)." A bare name list is filler.
- **Every Decision Needed item has three parts.** The *question* (phrased
  as a yes/no or a choice), the *options* (with their real tradeoffs —
  not just "pros and cons"), and your *recommendation with reasoning*.
  Two-line decision items mean the meeting will hash this out in real
  time instead of moving forward.
- **Agenda items are specific, not categories.** "Discuss roadmap" is not
  an agenda item. "Decide whether Q4 includes the mobile rewrite — eng
  capacity is the gating constraint" is. Time-box matches the depth of
  the item: decisions get 15-20m; FYIs get 2-5m.
- **Pre-read links are named, not vague.** "Latest usage data" is useless;
  "Q3 usage review (DAU dashboard, updated Monday)" tells the attendee
  what they're clicking. If you don't have the link, put a placeholder
  and flag it as an Open Question.
- **Open Risks names the concrete failure mode.** "Meeting could go long"
  is noise. "Risk: Priya and Marcus disagreed on auth approach in the
  retro — put their item first so we don't lose time if they re-open
  that debate" is signal.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "meeting_agenda"`
- `document_id: <slug>`
- `summary_for_user: <one-line describing meeting + top decision(s) needed>`

**STOP after calling AwaitReview.** No further text in this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each
revision. On approval, the skill completes.
