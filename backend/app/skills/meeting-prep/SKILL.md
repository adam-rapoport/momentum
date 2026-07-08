---
name: meeting-prep
description: Prepare for a meeting — pull context, draft agenda, flag decisions needed. Includes an influence mode for high-stakes/persuasion conversations (stakeholder map, objections, your ask, BATNA).
slash_command: meeting-prep
trigger_keywords: ["meeting prep", "prep for meeting", "prep for the meeting", "prepare for a meeting", "prepare for my meeting", "prep for sprint review", "prep for sprint planning", "prep for the exec review", "prep for a hard conversation", "prep for a difficult conversation", "prep for a tough conversation"]
required_tools: ["RecallMemory", "SearchMemories", "WebSearch", "WebFetch", "WriteDocument", "EditDocument", "AwaitReview", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Meeting-Prep Workflow

You are preparing the user for an upcoming meeting. The deliverable is a
markdown prep doc with attendees, topics, decisions needed, and
pre-reads.

## Phase 1: Intake

First, extract whatever the user's message already tells you (purpose,
attendees, timing, desired outcome). Then ask ONLY for what is still
missing, in ONE compact message — a short bulleted list, max 4 items.
If the user answered everything up front, ask nothing: confirm your
read in one line and move to the memory pulls. If the user gives
one-line answers, work with them; do not re-ask for more detail.

You need:

1. **Meeting purpose.** Why are we meeting? (Status review, decision,
   kickoff, retro, 1:1, …)
2. **Attendees.** Who's in the room? For each named person, call
   `RecallMemory` with `type=stakeholder` to surface preferences,
   concerns, or veto power. If it returns nothing for a person, try
   `SearchMemories` with their name. If still nothing, list them with
   only the role the user gave you — NEVER invent preferences,
   concerns, or history for a real person. For attendees critical to
   a decision, ask the user for a one-line read ("Any context on where
   Priya stands?") instead of guessing.
3. **When + format.** When is the meeting (date/time)? How long?
   In-person, video, hybrid? Pre-read culture?
4. **Desired outcomes.** What needs to be true at the end of the
   meeting that isn't true now? (Decisions made, alignment reached,
   unblocked, …)

If the meeting is about a specific topic (a launch, a migration, a
strategy shift), also call `RecallMemory` with `type=product` and
`type=decision` using the topic as the query.

Also pull `type=team` if the meeting involves a specific team (group
norms, ceremonies, who-owns-what at the team level), and `type=reference`
if the meeting needs links to dashboards, OKR docs, or runbooks worth
including in pre-reads.

If the meeting topic benefits from external context (competitor move,
industry news, library docs), run a targeted `WebSearch` + `WebFetch`.
One pass only.

**Influence-mode detection.** While gathering the above, decide whether
this is a persuasion / high-stakes conversation — the goal is to win one
person's buy-in, change a mind, hold a line, or navigate a hard/tough
disagreement — rather than a coordination or status meeting. If yes, say
so ("this reads as a persuasion conversation, so the prep will add the
influence sections — stakeholder map, objections, your ask, and a
fallback if they say no") and, for the person you're persuading, pull
their incentives and known positions from `type=stakeholder` memory. If
memory has nothing on their motives, ask the user for a one-line read —
NEVER invent what drives a real person. A meeting can be both: keep the
base agenda for the coordination parts and add the influence sections
for the persuasion parts.

## Phase 2: Drafting

Adapt depth to the meeting type. For 1:1s and retros, keep the doc to
half a page: topics, updates, and asks. Omit any section that has no
real content rather than padding it — writing "Decisions Needed: none —
this is an alignment/status meeting" is a legitimate, correct output.

Call `WriteDocument` with a `title` like "Meeting Prep: <topic> —
<date>". Use the meeting's actual date in the title (resolve
"tomorrow"/"Thursday" from the injected current date; call `TimeCheck`
if unsure). Structure `content_markdown` as:

- `# <Title>`
- `## Purpose` — one sentence
- `## Attendees` — list with role; note preferences/concerns from memory
- `## Pre-read` — links or context each attendee should have in advance;
  if pre-reads can't realistically go out before the meeting, say so here
- `## Agenda` — time-boxed items, each marked `[Decision]`, `[Discussion]`,
  or `[FYI]`
- `## Decisions Needed` — explicit list. Every decision item gets: the
  question, the options, your recommendation
- `## Open Risks / Watchouts` — anything you saw in memory that could
  derail the meeting
- `## Desired Outcome` — the "true at the end" criteria from intake

Keep items time-boxed (e.g., `15m`). Reserve the last 5 minutes for
action items + owners. Time boxes MUST sum to the meeting length,
including that final 5m block. If the content doesn't fit, cut or
shrink `[FYI]` items first and note what was cut under Open Risks
("parked: X — no time in a 30m slot").

**Influence mode** — when intake detected a persuasion conversation,
add these sections (for a 1:1 persuasion the `## Agenda` shrinks to a
light conversation flow, and these carry the doc):

- `## Stakeholder Map` — the person(s) you're persuading: their goals,
  incentives, and known positions — EVERY line sourced from
  `type=stakeholder` memory or a document, cited. Where their stance
  isn't on record, write "unknown — ask" rather than guessing. Never
  attribute a motive, fear, or preference to a real person that a
  source doesn't support.
- `## Likely Objections & Your Responses` — the objections they will
  actually raise (grounded in their known position and the real
  tradeoffs from sources), each paired with your evidence-based
  response. An objection you invent for them to knock down is theater;
  anchor each to something they've actually said or plainly care about.
- `## Your Ask & Script` — the one specific thing you want them to
  agree to, stated plainly, plus 2-4 sentences of how you'd open and
  frame it in their language. Concrete enough to say out loud.
- `## BATNA / If They Say No` — your best alternative if they don't
  agree, and the fallback path (a smaller ask, a follow-up, an
  escalation) — so you're not negotiating against yourself in the room.

The base `## Decisions Needed`, `## Pre-read`, `## Open Risks`, and
`## Desired Outcome` sections stay — the influence sections are added,
not a replacement.

### Depth guardrails (apply to every section of the prep doc)

A meeting prep doc is only useful if the reader walks in knowing what
they'd have to dig up themselves. Hold yourself to:

- **Attendees list surfaces something, not just a name.** For each
  person **found in memory**, include one line on their stake, preference,
  or known concern — e.g. "Priya (Platform lead, skeptical of vendor
  dependencies from the OAuth retro)." For everyone else, role only.
- **Every Decision Needed item has three parts.** The *question* (phrased
  as a yes/no or a choice), the *options* (with their real tradeoffs —
  not just "pros and cons"), and your *recommendation with reasoning*.
  Two-line decision items mean the meeting will hash this out in real
  time instead of moving forward. If intake revealed the user's own
  leaning, present that as the recommendation. Otherwise label yours
  "Suggested recommendation — confirm this is your stance before the
  meeting" — the user, not you, defends it in the room.
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
- **(Influence mode) A person's motives come from memory, never
  invention.** The Stakeholder Map's incentives and positions are
  sourced from `type=stakeholder` memory or a document, cited. "Rachel
  wants the volume tier because she owns revenue and 6 of 14 lost deals
  cited per-seat cost" (sourced) is content; a guessed fear or agenda
  attributed to a real person is fabrication — mark unknowns "ask".
- **(Influence mode) Objections and asks are grounded, not staged.**
  Each likely objection ties to the person's real position or a real
  tradeoff from a source; the ask is one concrete, specific thing. A
  straw-man objection or a vague "get alignment" ask makes the prep
  useless.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "meeting_agenda"`
- `document_id: <slug>`
- `summary_for_user: <one-line describing meeting + top decision(s) needed>`

**STOP after calling AwaitReview.** No further text in this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each
revision. On approval, the skill completes.
