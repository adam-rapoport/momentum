---
name: release-notes
description: Turn a list of shipped items into customer-facing release notes grouped by theme.
slash_command: release-notes
trigger_keywords: ["release notes", "draft release notes", "write release notes", "changelog entry"]
required_tools: ["RecallMemory", "SearchMemories", "ListDocuments", "ReadDocument", "TimeCheck", "WriteDocument", "DraftMessage", "EditDocument", "AwaitReview"]
phases: ["intake", "drafting", "review"]
---

# Release-Notes Workflow

You are turning a list of shipped items (commits, PRs, feature rollouts)
into release notes for a chosen audience (customers, beta users, or the
internal team). The deliverable is ALWAYS a saved markdown document;
email or Slack variants are produced in addition, never instead.

## Phase 1: Intake

**Step 0 — pull memory first, then ask only what's still unknown:**
`RecallMemory` with `type="product"` (product narrative for themes),
`type="reference"` (docs/dashboards worth linking), and
`type="stakeholder"` / `type="team"` (voice norms);
`SearchMemories("release notes")` for past releases' style. Skip any
intake question memory already answers.

Then ask one at a time, skipping anything already supplied:

1. **What shipped.** A list of items — PR titles, commit messages,
   feature names, or a freeform list; the user will likely paste this.
   No list handy? Call `ListDocuments` and offer a recent sprint plan
   or roadmap doc as the source (`ReadDocument` it, confirm which items
   shipped). Also capture the version number or release date for the
   title (`TimeCheck` for today's date on a monthly roundup).
2. **Audience.** Customers? Beta users? Internal team? Each gets a
   different voice and depth.
3. **Channel.** Markdown doc only (for a /releases page), email, or
   short in-app/Slack message? Channel sets the length.
4. **Voice/tone.** If the user has a known style ("plain, no marketing
   adjectives"), surface it.

## Phase 2: Drafting

Group the shipped items into themes (3-6). Bad: a flat list of every
PR. Good: "Faster search," "Easier sharing," "Polish & fixes." Each
shipped item lands under one theme.

Tools:

- **Always** call `WriteDocument` with `title` like "Release Notes:
  <month> <year>" or "v<version> Release Notes" — the saved doc is the
  deliverable regardless of channel; the user keeps a copy to edit and
  share.
- **Email channel** → ALSO call `DraftMessage` with `platform="email"`,
  `subject="What's new in <product>"` (or similar). (Section 7 prefers
  `DraftEmail` for real Gmail drafts; release notes go out through a
  marketing/announcement tool, not the PM's own Gmail — use
  `DraftMessage`, and `DraftEmail` only if the user explicitly asks for
  a Gmail draft.)
- **Slack / in-app channel** → ALSO `DraftMessage` with
  `platform="slack"` (concise variant).
- `DraftMessage` requires a `recipient`. Use the audience label from
  intake — "All customers (mailing list)" for email, "#product-updates"
  for Slack — unless the user named one. Don't ask a separate question.
- Default to one canonical version. If the user asked for terse AND
  detailed variants, put both in ONE `WriteDocument` under "## Terse
  version" / "## Detailed version" headings; call `AwaitReview` once.

Structure (adjust depth to channel):

- **Headline** — one line. The "big thing" in this release. If there
  isn't one, that's fine — the headline can be the theme that has the
  most under it.
- **Action required / breaking changes** — ONLY if a shipped item
  changes existing behavior or requires a user step (re-login,
  migration, deprecation). Put it directly under the headline, never
  buried inside a theme. Omit the section entirely when nothing
  qualifies.
- **Themes** — for each:
  - `### <Theme name>` — written as the user benefit, not the feature
    name ("Find docs faster" beats "Improved search")
  - 1-3 sentences explaining what changed and why it helps
  - Bulleted list of the actual shipped items underneath, in plain
    English. Single-item theme: fold the item into the paragraph — no
    bullet restating the sentence above it.
- **Polish & Fixes** — a section for the small stuff (bullets, terse)
- **What's Next** — optional, only if the user has something to tease

### Depth guardrails

Release notes either get read or they don't, and they get read when
they tell the user what's *new for them*. Hold yourself to:

- **Lead with the user benefit, not the feature name.** "Bulk export"
  is a feature; "Pull every report from the past quarter in one click"
  is a benefit. The benefit goes in the headline.
- **Never invent a benefit you can't see in the input.** If a shipped
  item is too cryptic to translate into a user benefit (e.g. "fix: null
  deref in parser"), do NOT guess what it does for users. Collect all
  such items and ask the user to gloss them in ONE batch before
  drafting ("What do these 3 mean for users?"). Only park a cryptic fix
  under Polish & Fixes if its user impact is unambiguous.
- **Cut adjectives.** "Powerful new search" is filler. "Search now
  matches partial words and ranks recent docs higher" is the actual
  thing. If you delete "powerful / improved / enhanced / new" and the
  sentence dies, the sentence wasn't saying anything.
- **Each shipped item gets one line, max.** If it needs two lines, it
  belongs in its own theme, or it's actually two items.
- **Match channel length.** A 12-item release is a full email or doc.
  A 1-item release is a single Slack sentence. Don't pad short releases
  to look bigger.
- **Skip internal-only changes.** Refactors, infra work, test-coverage
  improvements don't go in customer/beta notes — ask if uncertain. When
  the audience is the internal team, include them.

### Customer-facing hygiene (customer and beta audiences)

- **Never name a customer or design partner** unless the user
  explicitly approved the mention — "three design partners" is safe;
  names require consent and tell every other customer they're excluded.
- **Scrub internal language.** Engineering/standup jargon ("data
  joins", "eval gates"), internal QA mechanisms, and sprint numbers
  never appear in customer copy — no sprint numbers in public titles.
- **Qualify beta-only features as beta** ("in beta", "rolling out to
  beta users") — never write a beta feature as generally available.
- **If the audience was assumed rather than answered** ("use your best
  judgment"), state the assumed audience and channel in the
  `AwaitReview` summary so the user can catch a wrong guess.

## Phase 3: Review

Immediately after saving the draft, call `AwaitReview` with:
- `deliverable_kind: "release_notes"`
- `document_id: <slug>` (the `WriteDocument` slug — you always have one)
- `summary_for_user: <one line: audience + channel + headline theme,
  flagging any assumed audience/channel as "assumed">`

**STOP after calling AwaitReview.** No further text this turn.

Revisions go through `EditDocument` for the saved doc (and
`DraftMessage` again for a message variant). Re-call `AwaitReview`
after each. On approval, the skill completes.
