# Handoff: Momentum Full App Redesign — "Graphite & Phosphor"

## Overview

A complete redesign of the Momentum desktop app (Tauri + Next.js frontend) covering the
entire experience: chat workspace, empty home state, skill workflows (badge, tool calls,
approval bar), the merged Memory/Documents context panel, settings, and onboarding.
The design targets a **macOS-native feel** (traffic lights, draggable titlebar regions, no
web-style header) with the modern look of current AI apps, plus a measured retro layer:
bitmap pixel icons, a pixel display font for section labels, and dithered dividers.

## About the Design Files

The files in this bundle are **design references created in HTML** — interactive prototypes
showing intended look and behavior, **not production code to copy directly**. The task is to
recreate these designs inside the existing Momentum codebase
(`frontend/` — Next.js App Router + React + Tailwind) using its established patterns:
existing components (`Sidebar.tsx`, `ChatView.tsx`, `ChatInput.tsx`, `ToolCallBlock.tsx`,
`ApprovalBar.tsx`, `MemoryPanel.tsx`, `DocumentsPanel.tsx`, `Header.tsx`, settings/onboarding
pages), the existing API layer (`lib/api.ts`, `lib/store.ts`, `lib/types.ts`), and Tailwind
for styling (map the design tokens below to `tailwind.config.ts` theme extensions and CSS
variables in `globals.css`).

The prototype's React component decomposition (one file per zone) is a reasonable map onto
the existing component structure, but **follow the codebase's conventions, not the
prototype's** (the prototype uses inline styles and a fetch-and-eval Babel bootstrap purely
for prototyping convenience).

## Fidelity

**High-fidelity.** Colors, typography, spacing, radii, shadows, and interaction states are
final and should be matched closely. Exact hex values, px sizes, and state behaviors are
specified below. The only intentionally-unspecified areas: real data wiring (the prototype
uses canned demo data) and the actual streaming protocol (the prototype simulates it).

---

## Design Tokens

Define as CSS variables on `:root` / `[data-theme="dark"]` in `globals.css`, and expose
through Tailwind. The app must support **both themes**, user-toggleable, with an in-app
toggle (moon/sun button in the sidebar footer) — persist the choice (e.g. localStorage +
`data-theme` attribute on `<html>`).

### Colors — light theme

| Token | Value | Use |
|---|---|---|
| `--bg-app` | `#F2F3F3` | window background, toolbar |
| `--bg-panel` | `#EAEBEB` | sidebar, context panel |
| `--bg-surface` | `#FFFFFF` | cards, composer, active rows |
| `--bg-raised` | `#F7F8F8` | hover rows, tool blocks, code wells |
| `--bg-inset` | `#E3E4E4` | inset wells, segmented-control track |
| `--text` | `#17181A` | primary text |
| `--text-muted` | `#65696E` | secondary text, section labels |
| `--text-dim` | `#94999F` | tertiary text, metadata |
| `--border` | `#DEDFE0` | standard borders |
| `--border-strong` | `#C8CACC` | input borders, scrollbar thumbs |
| `--border-faint` | `#E8E9E9` | hairlines inside cards |
| `--warn` | `#B07C18` (soft `#F5E8C8`) | heavy-model chip, running state |
| `--danger` | `#C2452E` (soft `#F6DCD5`) | errors, delete confirm |
| `--ok` | `#0F9D63` (soft `#DCF0E6`) | connected, done states |

### Colors — dark theme

| Token | Value |
|---|---|
| `--bg-app` | `#131416` |
| `--bg-panel` | `#18191C` |
| `--bg-surface` | `#1F2024` |
| `--bg-raised` | `#26272C` |
| `--bg-inset` | `#0E0F10` |
| `--text` | `#ECEDEE` |
| `--text-muted` | `#9BA0A6` |
| `--text-dim` | `#61656C` |
| `--border` | `#2B2D31` |
| `--border-strong` | `#3C3F45` |
| `--border-faint` | `#232529` |
| `--warn` | `#D9A93F` (soft `#38300F`) |
| `--danger` | `#E0684F` (soft `#3D1B12`) |
| `--ok` | `#2ECC8C` (soft `#143726`) |

### Accent system

Default accent: **pixel green `#0F9D63`**. The user-selected base accent is derived into
theme-aware variants with CSS `color-mix(in oklab, …)` (see `pm-app.jsx → accentVars()`):

- Light: `--accent` = base; `--accent-fg` `#FFFFFF`; `--accent-tint` = 15% accent on white;
  `--accent-tint-2` = 8% on white; `--accent-text` = 82% accent mixed with black (AA on light bg).
- Dark: `--accent` = 78% accent mixed with white; `--accent-bright` = 65% with white;
  `--accent-fg` `#0B0D0E`; tints = 26% / 16% accent on `#1A1B1E`; `--accent-text` = 55% with white.

Alternative accents offered in the prototype: `#2563EB` (blue), `#D9622B` (orange), `#7A5AE0` (violet).

### Typography

| Role | Font | Notes |
|---|---|---|
| UI | **Schibsted Grotesk** (Google Fonts) | 400–700; base 14px / line-height 1.5 |
| Mono | **IBM Plex Mono** | tool calls, keys, costs, metadata |
| Pixel | **Silkscreen** | section labels ("eyebrows") ONLY — never body text |

Scale: body 14px; assistant messages 14.5px / 1.62; secondary 12–12.5px; metadata/mono
10.5–11.5px; chat title in toolbar 13.5px/650; settings pane titles 16.5px/700;
home greeting 27px/700/-0.02em; onboarding headlines 20–26px/700.

**Section labels (`PxLabel`)**: Silkscreen 10.5px, weight 700, uppercase,
letter-spacing `0.005em`, color `--text-muted`. When retro = off, falls back to
IBM Plex Mono 12px / 600 / 0.06em tracking.

### Spacing, radii, shadows

- Radii: 6 (sm) / 10 (default) / 14 (lg, cards & approval card) / 20 (xl, composer); pill 999.
- Shadows (light):
  - card: `0 1px 2px rgba(20,24,28,.05), 0 6px 20px -8px rgba(20,24,28,.08)`
  - composer: `0 1px 2px rgba(20,24,28,.04), 0 10px 32px -12px rgba(20,24,28,.14)`
  - popover: `0 2px 6px rgba(20,24,28,.08), 0 20px 50px -16px rgba(20,24,28,.22)`
  - dark equivalents use black at 0.3–0.75 alpha.
- Layout constants: sidebar 264px; context panel 312px; toolbar 48px; chat column max-width 760px; home column max-width 640px.
- Focus ring: `box-shadow: 0 0 0 2px var(--bg-app), 0 0 0 4px var(--accent)` on `:focus-visible`.
- Selection: `::selection { background: var(--accent-tint); color: var(--accent-text); }`

### Retro layer (three levels: off / subtle / full — "subtle" is default)

1. **Pixel icons** — every icon is a 9×9 bitmap rendered as SVG `<rect>`s with
   `shape-rendering: crispEdges` (see `pm-kit.jsx → PM_BITMAPS`). Full set: plus, search,
   gear, send, stop, check, x, chevrons, doc, mail, calendar, sparkle, tag, user, users, box,
   link, brain, globe, clock, floppy, panel, pencil, trash, arrowUp, bolt, plug, sun, moon.
   The logo is a 9×9 double-chevron in `--accent-bright`.
2. **Dither dividers** (`DitherRule`) — 2px-high checkerboard via
   `conic-gradient(currentColor 25%, transparent 0 50%, currentColor 0 75%, transparent 0)`,
   `background-size: 4px 4px`, color `--border-strong` at 0.8 opacity. 4px high at "full".
   Plain 1px `--border` line when retro = off.
3. **Pixel font labels** — as specified above.
4. At retro "full": status dots and avatars become squares (radius 0/6) instead of circles.
5. The approval card's top edge: 5px dither strip in accent color (3px solid bar when off).

---

## Screens / Views

### 1. App shell

Three-zone layout: **Sidebar (264px) | Main column | Context panel (312px, collapsible)**.
The sidebar header is the macOS titlebar region (traffic lights drawn in the prototype —
in Tauri use the real window controls; keep `-webkit-app-region: drag` on the
sidebar header and the toolbar). No web-style header anywhere.

### 2. Toolbar (48px, replaces `Header.tsx`)

Left: session title (13.5px/650, ellipsized) + **skill chip** when a skill is active —
accent-tinted pill, mono, `/<skill> · <phase>` with a pulsing accent dot;
tooltip explains `/cancel-skill`.
Right side, in order: **model chip** (mono pill — warn-tinted with dot for heavy model,
dim for light; shows short name e.g. "Scout", "Gemini 3 Pro"), **session cost** in mono
(`$0.0214`, 4 decimals, `--text-dim`), **local status** (green dot + "local" mono label,
tooltip "Backend connected on localhost:8000"), **context-panel toggle** icon button
(active state = accent tint).

### 3. Sidebar (`Sidebar.tsx`)

- Header: traffic lights, then logo + wordmark (Silkscreen "MOMENTUM" 11px when retro on).
- **New chat** button: full-width primary (accent bg, white text, left-aligned label,
  plus icon, right-aligned `⌘N` hint at 70% opacity). 34px tall, radius 8.
- **Search field**: 30px, `--bg-app` fill, inset pixel search icon, placeholder "Search chats".
  Filters sessions live.
- **Session list** grouped by recency: Today / Yesterday / This week / Earlier, each with a
  `PxLabel` header. Rows 32px, radius 7: inactive = transparent, muted text, weight 450;
  hover = `--bg-raised`; active = `--bg-surface` + card shadow + faint border, weight 600.
  Sessions with an active skill show a 6px accent dot before the title.
  Hover reveals rename (pencil) and delete (trash) micro-buttons (22px); delete is
  two-step — first click turns the button into a red "Sure?" pill.
  Rename swaps the row for an inline input (accent border + tint ring; Enter commits, Esc cancels).
- **Footer** (above: dither rule): avatar circle (initial on accent tint, square at retro full),
  display name 12.5px/600, "local · encrypted" mono caption, then **theme toggle**
  (moon/sun icon button) and **settings gear**.

### 4. Home / empty state (new chat)

Vertically centered, max-width 640, in a scroll container (safe on short windows).
Logo (28px), time-aware greeting "Good morning, Adam" (27px/700), subline
"What are we moving forward today?" (13.5px muted). Below: the **composer** (big variant,
autofocused), then a responsive grid (`repeat(auto-fit, minmax(150px, 1fr))`) of six
**skill shortcut cards**: white cards, radius 10, card shadow, pixel icon in accent,
12.5px/550 label; hover = accent border. Clicking seeds the composer with `/<command> `
(does not send). Footer caption: "Type / in the composer to see all 10 skills" with a
`<kbd>` styled key.

### 5. Composer (`ChatInput.tsx`)

Floating card: `--bg-surface`, radius 20, composer shadow, 1px border (accent when the
draft starts with `/`). Autosizing textarea (max 220px), placeholder
"Message Momentum — or type / for skills". When draft is a command: text renders in mono,
accent color, and a left-aligned mono hint appears: "skill turn → routes to heavy model".
Bottom row: hints (`⏎ send · ⇧⏎ newline` as kbd chips) + a 32px circular send button
(accent when nonempty, inset gray disabled; square-ish radius 8 at retro full).
While streaming the send button becomes a **stop button** (black/inverted, square pixel
stop glyph) that truncates the response mid-stream and leaves a mono "■ Stopped by you" note.

**Slash menu**: opens above the composer when draft matches `/^\/[a-z0-9-]*$/i`;
popover (radius 12, pop shadow) with `PxLabel` header "SKILLS & COMMANDS"; rows show
`/command` in mono 12.5/600 + description 12px muted; prefix-filtered; ↑/↓ to move
(selection = accent tint, command text in accent), Enter/Tab to autocomplete, Esc dismisses.

### 6. Conversation (`ChatView.tsx`, `MessageBubble.tsx`)

Column max-width 760, centered.
- **User messages**: right-aligned bubbles, max-width 78%, `--bg-surface`, 1px border,
  radius `14 14 4 14`, card shadow, 14px.
- **Assistant messages**: flat/document style — no bubble. 26px logo avatar chip
  (surface bg, 1px border, radius 8) + body 14.5px/1.62 with markdown
  (bold, lists, inline code, strikethrough; h4-style eyebrows). While streaming, a 7×15px
  accent **block cursor** blinks at the text end (steps animation, 0.9s).
- **Thinking row**: avatar with pulsing logo + mono "thinking…" 12px dim.
- Entrance animation: 4px fade-up, 0.22s ease; honor `prefers-reduced-motion`.
- **Autoscroll**: pinned to bottom while within 100px; scrolling up unpins and shows a
  floating "↓ Jump to latest" pill (inverted colors, bottom-center).

### 7. Tool call block (`ToolCallBlock.tsx`)

Collapsed row inside the conversation flow: `--bg-raised`, 1px faint border, radius 9.
Mono 11.5px: pixel icon (per tool: brain=memory, globe=web, doc=create-document,
calendar, floppy=save, tag=tickets, mail, clock), tool name 600, compacted input
(`key: value · key: value`, 48-char truncation) in dim, then status — colored dot
(amber pulsing = running, green = done, red = error) + uppercase 10px label and a chevron
that rotates when expanded. Expanded: INPUT / OUTPUT sections (`PxLabel` headers) with
pretty-printed JSON in `--bg-inset` wells, mono 11px; output capped at 180px with scroll.
Error blocks default to expanded.

### 8. Approval bar (`ApprovalBar.tsx`)

Replaces the composer when `awaiting_review` is set. Card: accent 1px border, radius 14,
composer shadow, **5px dithered accent strip across the top**. Header: pulsing accent dot +
headline by kind ("Ready for your review" / "Approve to send this email" /
"Approve to send these invites") + deliverable-kind chip (mono, accent tint).
- Deliverable kind: summary text + an embedded **doc row** (`--bg-raised`, doc icon, title,
  "Open in Google Docs ↗" accent link).
- Email kind: a preview well with To / Cc / Subject grid (56px label column, mono values)
  and body snippet under a hairline.
Actions: primary **"Looks good" / "Send email"** (check icon), secondary **"Make changes"**,
ghost **"Start over" / "Cancel"**. "Make changes" swaps actions for an inline revision
textarea (accent border + ring; Enter submits as `/revise <text>`, Esc backs out) +
"Send revision" primary.

### 9. Context panel (merged `MemoryPanel.tsx` + `DocumentsPanel.tsx`)

Single right panel, `--bg-panel`, left border. Header row (48px): `PxLabel` "CONTEXT" +
close X. Below: **segmented control** (inset track radius 9, 3px padding; active segment =
surface bg + card shadow) with two tabs: **Memory** (brain icon) and **Documents** (doc icon).
- **Memory tab**: grouped by type — Stakeholders, Decisions, Product, Team, Lessons,
  References — each header = pixel icon + `PxLabel` + count in mono. Rows: title 12.5/600
  ellipsized + 2-line-clamped summary 11.5 muted. Click selects (surface bg + shadow);
  click again deselects. Selection opens a **detail drawer** pinned to the panel bottom
  (max 46% height, surface bg, sticky title bar with close X): tag chips (mono pills),
  markdown body 12.5/1.55, "Updated <date>" mono caption.
- **Documents tab**: grouped "Google Docs" / "On this Mac". Rows: doc icon, title
  12.5/600, mono timestamp; Google rows get an "Open ↗" bordered accent micro-link,
  local rows a dim mono "local" tag.

### 10. Settings (modal sheet, replaces settings page)

Centered modal over a `rgba(10,12,14,0.45)` + blur(3px) scrim; click-outside and Esc close.
Window: 820×560 max, radius 14, pop shadow, 1px border. Left nav rail (186px, `--bg-panel`):
traffic lights, `PxLabel` "SETTINGS", then nav items (32px rows, icons: bolt, plug, globe,
user, box) with the same active treatment as sidebar rows. Panes:
- **Models** — two cards: Light model (bolt icon; "Fast everyday turns — chat, recall, tools")
  and Heavy model (brain icon, accent; "Big asks — drafting, long reasoning"). Each shows
  provider name, masked key (`gsk_••••…mPq3`), "last used" mono caption, "connected" chip;
  "Change/Set up" opens inline editing: provider pill-buttons (with Free/Free tier/Soon
  badges; unavailable disabled at 45% opacity), mono key input with provider-specific
  placeholder + help text ending "Stored encrypted on this Mac — never leaves it."
- **Integrations** — cards for Google (connected: account + last-used mono caption,
  red ghost Disconnect), Slack/Linear/Jira ("Soon", disabled).
- **Web search** — Tavily (Free tier) / Perplexity (Paid) cards with active chip + Use/Remove.
- **Profile** — name/role/company inputs (110px label grid) + "Replay onboarding" card.
- **About** — logo + wordmark; key/value rows (Version, Shell, Backend, Data path, Keys) in
  mono; dither rule; privacy paragraph.

### 11. Onboarding (full-window takeover)

Five steps: Welcome → Light model → Heavy model → Tools → Done. Draggable top strip with
traffic lights. Column max-width 640.
- **Stepper** (steps 2–4): numbered 20px squares/circles — done = accent fill + check,
  current = accent tint + accent border, future = inset; connected by 1px lines.
- **Welcome**: 44px logo, wordmark, value prop, primary CTA "Set up in 2 minutes" (lg),
  mono caption "you'll need one free API key · no account, no cloud", and an underlined
  dim "Skip — explore with no key" escape hatch.
- **Model steps**: `PxLabel` eyebrow ("STEP 2 · LIGHT MODEL"), 20px headline, helper text.
  Provider radio-cards (radius 12; selected = accent border + tint bg + 3px tint ring):
  radio dot, name + badge chip, description, mono pricing line. Key input below (40px,
  mono) with **live format validation** — border turns `--ok` green + check caption
  "Format looks right — we'll verify on first use." when prefix/length match
  (Groq: `gsk_`, ≥50 chars; Gemini: `AIza`, 39 chars). Continue gated on valid light key;
  heavy step and tools step have "Skip for now".
- **Tools**: same integration cards, optional, "Finish setup →".
- **Done**: big accent check disc, "You're set", summary card (Light model / Heavy model /
  Google / Memory & data rows), suggested first prompts, "Start working →".

---

## Interactions & Behavior

- **Streaming lifecycle** (per agent turn): thinking row → tool block appears in
  "running" (amber, pulsing) → flips to "done" with output → text streams in with the
  block cursor → commits as a message. Stop button truncates and commits partial text.
- **Skill turns**: any `/command` message routes to the heavy model (surface this in the
  composer hint); skill state shows as toolbar chip with phase; approval kinds:
  deliverable review, send_email, create_event.
- **Approve / revise / restart** map to `/approve`, `/revise <feedback>`, `/restart`-or-`/cancel`.
- **Keyboard**: ⌘N new chat; Enter send / Shift+Enter newline; slash-menu ↑↓/Enter/Tab/Esc;
  Esc closes settings; approval revision Enter/Esc.
- **Theme toggle**: sidebar footer moon/sun; flips `data-theme` on `<html>`; persists.
- Transitions: backgrounds/borders 0.10–0.15s ease; chevron rotation 0.12s; toggle knob
  0.15s; respect `prefers-reduced-motion` for blink/pulse/entrance animations.

## State Management

Maps onto the existing `lib/store.ts` / API layer:
- Sessions: id, title, group (recency bucket), model (last-used), cost, skill
  `{name, phase}`, awaitingReview, messages (user | assistant | tool).
- UI state: activeSessionId, contextPanelOpen (persist), contextTab, settingsOpen+pane,
  theme (persist), accent (persist), retroLevel (persist; default "subtle").
- Streaming state machine per session: idle | thinking | tool-running | streaming.
- Settings: model slots (provider, masked key, status, lastUsed), integrations,
  search provider, profile.

## Assets

No external images. All icons are inline 9×9 bitmap SVGs (definitions in `pm-kit.jsx →
PM_BITMAPS`); the logo is the 9×9 double-chevron (`PmLogo`). Fonts from Google Fonts:
Schibsted Grotesk, IBM Plex Mono, Silkscreen — bundle them locally for the desktop build
rather than loading from the network.

## Reference screenshots (`screenshots/`)

Captured from the prototype at ~924px width (the real app window will be wider; treat
layout proportions, not absolute crops, as the reference):

- `light-home.png` / `dark-home.png` — empty home state with skill shortcuts
- `light-chat-prd-approval.png` — PRD session: tool blocks + deliverable approval card + active-skill toolbar chip
- `light-chat-email-approval.png` / `dark-chat-email-approval.png` / `dark-chat-prd-approval.png` — email & PRD approval cards
- `light-slash-menu.png` — slash-command menu over the composer
- `light-settings-models.png` / `light-settings-integrations.png` — settings sheet panes
- `onboarding-welcome.png` / `onboarding-light-model-step.png` — onboarding wizard

## Files

| File | Contents |
|---|---|
| `Momentum App.html` | entry: tokens (all CSS variables, both themes), global styles, bootstrap |
| `pm-kit.jsx` | pixel icon bitmaps, logo, Btn/IconBtn/Chip/PxLabel/StatusDot/DitherRule/Toggle/TextInput/Kbd, mini-markdown renderer |
| `pm-sidebar.jsx` | sidebar incl. session rows, rename/delete, search, footer + theme toggle |
| `pm-context.jsx` | merged context panel (Memory/Documents tabs, detail drawer) |
| `pm-chat.jsx` | conversation view, tool blocks, approval card, streaming sim, home state |
| `pm-composer.jsx` | composer + slash menu + send/stop |
| `pm-settings.jsx` | settings modal, all five panes |
| `pm-onboarding.jsx` | onboarding wizard |
| `pm-app.jsx` | shell: toolbar, layout, accent derivation (`accentVars`), theme wiring |
| `pm-data.jsx` | demo data (sessions, memories, documents, providers, commands) — reference for content tone & shapes only |

Open `Momentum App.html` in a browser to interact with the prototype while implementing.
(`tweaks-panel.jsx` is prototype-only review tooling — ignore it.)
