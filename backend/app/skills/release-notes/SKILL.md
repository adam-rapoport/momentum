---
name: release-notes
description: Turn a list of shipped items into customer-facing release notes grouped by theme.
slash_command: release-notes
trigger_keywords: ["release notes", "draft release notes", "write release notes", "changelog entry"]
required_tools: ["RecallMemory", "SearchMemories", "WriteDocument", "DraftMessage", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Release-Notes Workflow

You are turning a list of shipped items (commits, PRs, feature rollouts)
into customer-facing release notes. Output can be a markdown doc, an
email, or a Slack/in-app message — chosen in Phase 1.

## Phase 1: Intake

Ask one at a time, skipping anything already supplied:

1. **What shipped.** A list of items — PR titles, commit messages,
   feature names, or a freeform list. The user will likely paste this.
2. **Audience.** Customers? Beta users? Internal team? Each gets a
   different voice and depth.
3. **Channel.** Markdown doc (for a /releases page), email (sent via
   `DraftMessage` with `platform=email`), or short in-app/Slack
   message? Channel sets the length.
4. **Voice/tone.** If the user has a known style ("plain, no marketing
   adjectives"), surface it. Pull `type=stakeholder` for the audience
   or `type=team` for known voice norms.
5. **Variant preference.** Do they want one canonical version, or both
   a terse and a detailed variant to choose from? Default to one canonical
   version unless they ask.

Pull `type=product` (so themes match the product's narrative) and
`type=reference` (links to docs, dashboards, or feature pages worth
including).

## Phase 2: Drafting

Group the shipped items into themes (3-6). Bad: a flat list of every
PR. Good: "Faster search," "Easier sharing," "Polish & fixes." Each
shipped item lands under one theme.

Call the appropriate tool:
- **Markdown doc** → `WriteDocument` with `title` like "Release Notes:
  <month> <year>" or "v<version> Release Notes"
- **Email** → `DraftMessage` with `platform="email"`, `subject="What's
  new in <product>"` (or similar)
- **Slack / in-app** → `DraftMessage` with `platform="slack"` (concise
  variant)

Structure (adjust depth to channel):

- **Headline** — one line. The "big thing" in this release. If there
  isn't one, that's fine — the headline can be the theme that has the
  most under it.
- **Themes** — for each:
  - `### <Theme name>` — written as the user benefit, not the feature
    name ("Find docs faster" beats "Improved search")
  - 1-3 sentences explaining what changed and why it helps
  - Bulleted list of the actual shipped items underneath, in plain English
- **Polish & Fixes** — a section for the small stuff (bullets, terse)
- **What's Next** — optional, only if the user has something to tease

### Depth guardrails

Release notes either get read or they don't, and they get read when
they tell the user what's *new for them*. Hold yourself to:

- **Lead with the user benefit, not the feature name.** "Bulk export"
  is a feature; "Pull every report from the past quarter in one click"
  is a benefit. The benefit goes in the headline.
- **Cut adjectives.** "Powerful new search" is filler. "Search now
  matches partial words and ranks recent docs higher" is the actual
  thing. If you delete "powerful / improved / enhanced / new" and the
  sentence dies, the sentence wasn't saying anything.
- **Each shipped item gets one line, max.** If it needs two lines, it
  belongs in its own theme, or it's actually two items.
- **Match channel length.** A 12-item release is a full email or doc.
  A 1-item release is a single Slack sentence. Don't pad short releases
  to look bigger.
- **Skip internal-only changes.** Refactors, infra work, test coverage
  improvements don't go in customer-facing notes (they may belong in
  internal release notes — ask if uncertain).

## Phase 3: Review

Immediately after producing the draft, call `AwaitReview` with:
- `deliverable_kind: "release_notes"`
- `document_id: <slug>` (only when WriteDocument was used)
- `summary_for_user: <one line: channel + headline theme>`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument` (for docs) or `DraftMessage` again
(for messages). Re-call `AwaitReview` after each. On approval, the
skill completes.
