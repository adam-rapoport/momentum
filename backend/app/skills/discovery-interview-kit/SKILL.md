---
name: discovery-interview-kit
description: Prepare or synthesize discovery interviews — a non-leading interview guide before the calls, or a faithful interview snapshot after them.
slash_command: discovery-interview-kit
trigger_keywords: ["interview guide", "interview kit", "plan discovery interviews", "interview snapshot", "synthesize interview notes"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "WriteDocument", "EditDocument", "AwaitReview", "SaveMemory", "TimeCheck"]
phases: ["intake", "drafting", "review"]
---

# Discovery-Interview-Kit Workflow

You are helping with discovery interviews, on one of two sides —
intake determines which:

- **Guide** (before the calls): a research goal, the assumptions
  being tested, a screener, and a non-leading question flow an
  interviewer can run in the room.
- **Snapshot** (after the calls): a per-interview or per-round
  synthesis that keeps quotes verbatim, separates observation from
  interpretation, and names what changed your mind.

One deliverable per run. If the user wants both sides, do the one
they need now and offer the other as a follow-up. (For clustering a
pile of inbound feedback — tickets, surveys, reviews — point the
user at the feedback-synthesis skill instead; this kit is for
interviews you run.)

## Phase 1: Intake

FIRST, before asking anything (if neither the research topic nor the
side — guide vs snapshot — is clear, ask that one question, then):

1. Call `TimeCheck` — interview scheduling and research deadlines
   anchor to today.
2. Call `RecallMemory` with the topic as the query, once each for
   `type=product` (what's known about this workflow/feature today),
   `type=decision` (what's already decided — interviews that
   relitigate a decision need to know they are), and `type=lessons`
   (past research learnings on this surface). If a typed pull
   returns nothing, try one broader `SearchMemories` query, then
   move on — do not stall.
3. Read the PRIMARY sources in full: existing research notes (what's
   already been learned — don't re-ask it), and for the snapshot
   side, the interview notes/transcripts being synthesized — the
   snapshot is only as good as its coverage of them. Uploaded files
   live as reference memories; `ListDocuments` mostly shows
   generated deliverables — treat those as secondary.
4. Present what you found in 2-3 bullets ("Here's what's already
   known about <topic> — correct anything wrong"), then ask ONLY
   what's missing.

Ask the intake questions in at most TWO messages, skipping anything
already supplied. Even when the opening message plus documents cover
everything, the 2-3 bullet picture is NOT optional: post it — naming
the side (guide or snapshot), what's already known from prior
research, and (guide) the assumptions to test or (snapshot) which
notes you'll synthesize — and end your turn so the user can steer
before you draft.

Guide side, first message:
1. **What must these interviews teach you?** The decision the
   research feeds, and the riskiest assumption in it.
2. **Who are you talking to?** Segment, role, how many, and how
   they're being recruited.

Guide side, second message:
3. **Format.** Call length, moderated by whom, solo or shadowed?
4. **Off-limits.** Topics to avoid (pricing, unannounced features)?

Snapshot side, first message:
1. **Which interviews, and where do the notes live?** Pointers to
   docs beat retyping.
2. **What question was this round trying to answer?** The snapshot
   judges evidence against it.

## Phase 2: Drafting

### Guide side

Call `WriteDocument` with a `title` like "Interview Guide: <topic>"
and `content_markdown` structured as:

- `# <Title>`
- `## Research Goal` — the decision this research feeds, in one
  sentence, plus the 2-4 assumptions being tested — each phrased so
  an interview could falsify it.
- `## Participants & Screener` — who qualifies, who's excluded, and
  2-3 screener questions. Segment facts from sources; recruiting
  targets from the user.
- `## Question Flow` — timed sections (opener, context, core, wrap),
  each question open and behavior-anchored. Past behavior over
  hypotheticals: "walk me through the last time you…" beats "would
  you use…". Include the follow-up probes under each core question.
- `## What NOT To Do` — the guide's own guardrails: no pitching, no
  leading, no explaining the roadmap; plus any user-named off-limits
  topics.
- `## Capture Plan` — what gets recorded where, and the debrief
  ritual (who writes the snapshot, within what window).
- `## Open Questions` — gaps the sources couldn't fill.
- `## Memory Updates` — propose a `type=product` entry (the research
  goal + assumptions under test). Proposals until saved in Phase 3 —
  never mark one "Saved" in the doc.

### Snapshot side

Call `WriteDocument` with a `title` like "Interview Snapshot:
<round/participant>" and `content_markdown` structured as:

- `# <Title>`
- `## Round & Question` — which interviews this covers (count, from
  the notes — never inflated) and the research question they served.
- `## What We Heard` — per theme: the finding, how many participants
  it came from (counted over the notes), and 1-2 verbatim quotes
  with speakers. Quotes are exact, contiguous spans from the notes —
  paraphrase without quotation marks when you must compress.
- `## Observations vs Interpretations` — two lists, hard line: what
  participants said/did (sourced) vs what you infer it means
  (labeled inference, with what would confirm it).
- `## Surprises & Changed Minds` — what contradicted the going-in
  assumptions, tied back to the assumption it hit.
- `## Next Steps` — what this round settles, what it doesn't, and
  what the next round (or decision) should be.
- `## Open Questions` — gaps in the notes themselves.
- `## Memory Updates` — propose `type=lessons` entries (validated/
  falsified assumptions) and `type=product` (durable user facts).
  Proposals until saved in Phase 3 — never mark one "Saved" in the
  doc.

### Depth guardrails

- **Questions must be non-leading and behavior-anchored.** Every
  core question asks about past behavior or lived specifics; rewrite
  any "would you / do you think X is useful" into "tell me about the
  last time…". A guide that pitches the product is a demo script,
  not research.
- **Assumptions come from sources or the user.** The assumptions
  under test trace to a strategy doc, research notes, or the user's
  own words — never invented to fill the section.
- **Snapshot counts are counted.** "4 of 6 participants" only when
  the notes support the count over the FULL set; if the notes cover
  fewer interviews than the user mentioned, report the coverage gap
  instead of extrapolating.
- **No invented participants or quotes.** Every participant, quote,
  and detail in a snapshot exists in the notes. Example questions in
  a guide are fine; example ANSWERS presented as data are not.
- **Interpretations never wear observation's clothes.** The
  inference label is not optional — a snapshot whose interpretations
  read as findings poisons every doc downstream.
- **One follow-up per thin answer.** If the research goal or the
  notes' location is vague, ask at most ONE follow-up, then draft
  with what you have, marking unknowns.

## Phase 3: Review

Immediately after writing, call `AwaitReview` with:
- `deliverable_kind: "interview_kit"`
- `document_id: <slug>`
- `summary_for_user: <one line: side (guide/snapshot), topic, and the headline — assumptions under test or top finding>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument`; re-call `AwaitReview` after each.
On approval, offer to save the flagged Memory Updates yourself via
`SaveMemory` (guide: `type=product` for the research goal; snapshot:
`type=lessons` for settled assumptions, `type=product` for durable
user facts): one short confirmation listing the entries, then save
what the user okays. Then the skill completes.
