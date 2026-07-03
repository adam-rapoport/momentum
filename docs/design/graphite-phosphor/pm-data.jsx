// pm-data.jsx — demo data layer for the Momentum app redesign.
// Sessions, messages, memories, documents, commands, providers, integrations.

// ── Slash commands / skills ─────────────────────────────────────────────────
const PM_COMMANDS = [
  { command: 'write-prd', description: 'Draft a PRD through a guided workflow' },
  { command: 'stakeholder-update', description: 'Compose a stakeholder status update' },
  { command: 'meeting-prep', description: 'Build an agenda + talking points' },
  { command: 'release-notes', description: 'Turn shipped work into release notes' },
  { command: 'sprint-review', description: 'Summarize the sprint for review' },
  { command: 'user-story', description: 'Write user stories with acceptance criteria' },
  { command: 'quarterly-review', description: 'Assemble a quarterly business review' },
  { command: 'decision-log', description: 'Record a decision with context + options' },
  { command: 'feedback-synthesis', description: 'Cluster and synthesize user feedback' },
  { command: 'competitive-analysis', description: 'Research and compare competitors' },
  { command: 'approve', description: 'Approve the staged deliverable or action' },
  { command: 'revise', description: 'Request changes to the staged deliverable' },
  { command: 'cancel-skill', description: 'Exit the active skill workflow' },
];

// Home-screen shortcuts (subset, with display labels)
const PM_SKILL_SHORTCUTS = [
  { command: 'write-prd', label: 'Write a PRD', icon: 'doc' },
  { command: 'stakeholder-update', label: 'Stakeholder update', icon: 'mail' },
  { command: 'meeting-prep', label: 'Meeting prep', icon: 'calendar' },
  { command: 'feedback-synthesis', label: 'Synthesize feedback', icon: 'sparkle' },
  { command: 'release-notes', label: 'Release notes', icon: 'tag' },
  { command: 'decision-log', label: 'Log a decision', icon: 'check' },
];

// ── Providers & integrations (settings + onboarding) ────────────────────────
const PM_PROVIDERS = {
  groq: {
    id: 'groq', name: 'Groq', tier: 'light', badge: 'Free', badgeKind: 'ok',
    pricing: 'Free up to 14,400 requests / day · no credit card',
    description: 'Fast, free routine model. Good default to start with.',
    helpText: 'Sign in at console.groq.com, then "Create API Key".',
    keyHint: 'Starts with gsk_, ~56 chars', keyPrefix: 'gsk_', keyLength: [50, 80],
    available: true,
  },
  geminiFree: {
    id: 'geminiFree', name: 'Google Gemini', tier: 'heavy', badge: 'Free tier', badgeKind: 'ok',
    pricing: 'Free up to 1,500 requests / day · paid tier coming',
    description: 'Capable reasoning model on a generous free tier.',
    helpText: 'In Google AI Studio → "Get API key" → create.',
    keyHint: 'Starts with AIza, 39 chars', keyPrefix: 'AIza', keyLength: [39, 39],
    available: true,
  },
  openai: {
    id: 'openai', name: 'OpenAI', tier: 'both', badge: 'Soon', badgeKind: 'dim',
    pricing: 'Billed per token by OpenAI',
    description: 'GPT-4.x family. Planned.', available: false,
  },
  anthropic: {
    id: 'anthropic', name: 'Anthropic', tier: 'both', badge: 'Soon', badgeKind: 'dim',
    pricing: 'Billed per token by Anthropic',
    description: 'Claude family. Planned.', available: false,
  },
};

const PM_INTEGRATIONS = {
  google: {
    id: 'google', name: 'Google', sub: 'Docs, Gmail, Calendar',
    description: 'Read & draft Docs, summarize threads, check your week.',
    scopes: ['Docs (read/write)', 'Gmail (read)', 'Calendar (read)'],
    available: true,
  },
  slack: {
    id: 'slack', name: 'Slack', sub: 'Channels, DMs',
    description: 'Pull context from channels you choose.', available: false,
  },
  linear: {
    id: 'linear', name: 'Linear', sub: 'Issues, projects',
    description: 'Read your backlog, draft tickets.', available: false,
  },
  jira: {
    id: 'jira', name: 'Jira', sub: 'Issues, projects',
    description: 'Read your backlog, draft tickets.', available: false,
  },
};

const PM_SEARCH_PROVIDERS = [
  { id: 'tavily', name: 'Tavily', badge: 'Free tier', detail: '1,000 searches / month free' },
  { id: 'perplexity', name: 'Perplexity', badge: 'Paid', detail: 'Billed per request' },
];

// ── Memories ────────────────────────────────────────────────────────────────
const PM_MEMORY_TYPES = {
  stakeholder: { label: 'Stakeholders', icon: 'user' },
  decision: { label: 'Decisions', icon: 'check' },
  product: { label: 'Product', icon: 'box' },
  team: { label: 'Team', icon: 'users' },
  lessons: { label: 'Lessons', icon: 'sparkle' },
  reference: { label: 'References', icon: 'link' },
};

const PM_MEMORIES = [
  {
    id: 'mem-1', type: 'stakeholder', title: 'Sarah Chen — VP Sales',
    summary: 'Wants revenue framing; allergic to jargon. Prefers Tuesday updates.',
    tags: ['sales', 'exec'],
    body: 'Sarah reads updates on her phone between meetings — keep them under 200 words with the revenue impact in the first line.\n\n- Frame everything in pipeline / deal terms\n- Hates "synergy" and "alignment" — be concrete\n- Sends questions on Slack, expects same-day answers\n- Backs the mobile launch but worried about Q2 slippage',
    updated: 'Jun 8, 2026',
  },
  {
    id: 'mem-2', type: 'stakeholder', title: 'Marcus Webb — Eng Lead, Mobile',
    summary: 'Owns the iOS/Android codebase. Estimates conservatively, ships on time.',
    tags: ['eng', 'mobile'],
    body: 'Marcus pads estimates by ~20% and then beats them. When he flags a risk, take it seriously — he raised the push-notification dependency three weeks before it slipped.\n\nPrefers async written specs over meetings.',
    updated: 'Jun 5, 2026',
  },
  {
    id: 'mem-3', type: 'decision', title: 'Deferred offline mode to Q3',
    summary: 'Scope cut on May 28 to protect the Q2 launch date.',
    tags: ['mobile-launch', 'scope'],
    body: 'Decided in sprint planning May 28: offline mode moves to Q3. The sync-conflict edge cases were eating estimate confidence.\n\n**Options considered:** ship partial offline (rejected — confusing UX), delay launch 3 weeks (rejected — marketing committed), defer (chosen).\n\nSarah and Marcus both signed off.',
    updated: 'May 28, 2026',
  },
  {
    id: 'mem-4', type: 'decision', title: 'Pricing page A/B test winner',
    summary: 'Variant B (3-tier) beat control by 14% on trial starts.',
    tags: ['growth', 'pricing'],
    body: 'Ran Apr 14 – May 9. Variant B (3-tier with highlighted middle) lifted trial starts 14% (p < 0.01). Rolled out to 100% May 12.',
    updated: 'May 12, 2026',
  },
  {
    id: 'mem-5', type: 'product', title: 'Q2 mobile launch — scope',
    summary: 'iOS + Android parity, push notifications, biometric login. Offline deferred.',
    tags: ['mobile-launch'],
    body: 'Launch scope locked May 28:\n\n- Feature parity with web for core flows\n- Push notifications (deal alerts, mentions)\n- Biometric login (Face ID / fingerprint)\n- ~~Offline mode~~ → deferred to Q3\n\nTarget: July 8 App Store / Play Store.',
    updated: 'Jun 2, 2026',
  },
  {
    id: 'mem-6', type: 'product', title: 'Onboarding funnel baseline',
    summary: 'Signup → activated: 31%. Biggest drop at workspace-setup step (−42%).',
    tags: ['onboarding', 'metrics'],
    body: 'May cohort funnel:\n\n- Signup → email verify: 84%\n- Verify → workspace setup: 58% ← biggest drop\n- Setup → first project: 71%\n- Overall signup → activated: 31%\n\nHypothesis: workspace setup asks 6 questions before showing any value.',
    updated: 'Jun 6, 2026',
  },
  {
    id: 'mem-7', type: 'team', title: 'Design review cadence',
    summary: 'Crits Wednesdays 2pm. Priya owns the mobile design system.',
    tags: ['process'],
    body: 'Design crits happen Wednesdays 2pm PT. Priya Nair owns the mobile design system; loop her in before any new component work.',
    updated: 'Apr 22, 2026',
  },
  {
    id: 'mem-8', type: 'lessons', title: 'Launch comms: brief support first',
    summary: 'v2.3 launch generated 3× ticket volume because support saw it last.',
    tags: ['launch', 'support'],
    body: 'For v2.3 we announced before briefing support — ticket volume tripled for a week and CSAT dipped. For every launch since: support gets the brief 5 business days early, with a canned-response pack.',
    updated: 'Mar 30, 2026',
  },
  {
    id: 'mem-9', type: 'reference', title: 'North-star metric definition',
    summary: 'Weekly Active Workspaces (WAW) — workspace with ≥3 active members.',
    tags: ['metrics'],
    body: 'WAW = workspaces with ≥3 members each doing ≥1 qualifying action in a 7-day window. Qualifying actions: create/edit doc, comment, complete task. Dashboard: go/waw.',
    updated: 'Feb 11, 2026',
  },
];

// ── Documents ───────────────────────────────────────────────────────────────
const PM_DOCUMENTS = [
  { id: 'doc-1', backend: 'google_docs', title: 'PRD — Onboarding Checklist Redesign', updated: 'Today, 2:14 PM', url: '#' },
  { id: 'doc-2', backend: 'google_docs', title: 'Stakeholder Update — Week of Jun 8', updated: 'Today, 11:02 AM', url: '#' },
  { id: 'doc-3', backend: 'google_docs', title: 'Meeting Agenda — Thursday Planning', updated: 'Yesterday, 4:40 PM', url: '#' },
  { id: 'doc-4', backend: 'local', title: 'Release Notes — v2.4 (draft)', updated: 'Jun 6, 9:18 AM', url: null },
  { id: 'doc-5', backend: 'local', title: 'Decision Log — Offline Mode Deferral', updated: 'May 28, 3:55 PM', url: null },
];

// ── Sessions + message transcripts ──────────────────────────────────────────
// Message shapes:
//  { role: 'user'|'assistant', text }
//  { role: 'tool', name, input, output, isError }
const PM_SESSIONS = [
  {
    id: 's-prd',
    title: 'Onboarding drop-off PRD',
    group: 'Today',
    model: 'gemini-3-pro',
    cost: 0.0214,
    skill: { name: 'write-prd', phase: 'review' },
    awaitingReview: {
      kind: 'deliverable',
      deliverable_kind: 'prd',
      summary: 'Drafted "PRD — Onboarding Checklist Redesign" with problem framing, 3 solution options, and success metrics. The doc is in your Google Drive.',
      docTitle: 'PRD — Onboarding Checklist Redesign',
      url: '#',
    },
    messages: [
      { role: 'user', text: '/write-prd replace the 6-question workspace setup with a progressive checklist' },
      { role: 'assistant', text: 'Starting the **PRD workflow**. First, let me pull what we know about the onboarding funnel.' },
      { role: 'tool', name: 'RecallMemory', input: { query: 'onboarding funnel' }, output: 'Found: "Onboarding funnel baseline" — Signup → activated 31%, biggest drop at workspace-setup (−42%). Hypothesis: setup asks 6 questions before showing value.' },
      { role: 'tool', name: 'WebSearch', input: { query: 'progressive onboarding checklist activation benchmarks 2026' }, output: '5 results. Median signup→activation for B2B SaaS: 36–44%. Checklist-driven onboarding shows +8–15pp lift in 3 of 4 published case studies.' },
      { role: 'assistant', text: 'Here\u2019s my framing before I draft:\n\n**Problem.** 42% of verified signups abandon at workspace setup — six required questions stand between them and any value. That caps overall activation at 31% against a 36–44% benchmark.\n\n**Proposal.** Replace the gate with a 3-item progressive checklist that unlocks as the workspace is used: name your workspace → invite one teammate → create your first doc.\n\nI\u2019ll draft with three solution options (checklist, deferred questions, hybrid) and success metrics tied to **WAW**. Drafting now…' },
      { role: 'tool', name: 'CreateDocument', input: { title: 'PRD — Onboarding Checklist Redesign', backend: 'google_docs' }, output: 'Created https://docs.google.com/document/d/1xK…/edit — 1,840 words, 6 sections.' },
    ],
  },
  {
    id: 's-update',
    title: 'Q2 mobile launch update',
    group: 'Today',
    model: 'llama-4-scout',
    cost: 0.0031,
    skill: null,
    messages: [
      { role: 'user', text: 'Draft a status update for the Q2 mobile launch for Sarah — it slipped two weeks.' },
      { role: 'tool', name: 'RecallMemory', input: { query: 'Sarah Chen preferences' }, output: 'Sarah Chen — VP Sales. Revenue framing, under 200 words, impact first line, no jargon. Backs the launch, worried about slippage.' },
      { role: 'tool', name: 'RecallMemory', input: { query: 'Q2 mobile launch scope' }, output: 'Scope locked May 28: parity, push, biometric login. Offline deferred to Q3. Target July 8.' },
      { role: 'assistant', text: 'Draft, tuned to how Sarah reads:\n\n**Mobile launch: July 22 (was July 8) — no pipeline impact expected.**\n\nThe two-week slip comes from the push-notification provider migration Marcus flagged in May. Nothing sales-facing changes: demo environments stay on web, and the three enterprise deals waiting on mobile all close after July 22 anyway.\n\nWhat we protected: feature parity, push alerts for deal mentions, biometric login. What moved: offline mode was already deferred to Q3 — that\u2019s unchanged.\n\nAsk: if any active deal needs mobile before July 22, flag it this week and we\u2019ll arrange a TestFlight build.\n\n— Want me to send this as an email, or post it somewhere?' },
      { role: 'user', text: 'Email it to Sarah, cc me.' },
    ],
    // this session resumes with an email approval when opened
    awaitingReview: {
      kind: 'send_email',
      preview: {
        to: ['sarah.chen@acme.com'],
        cc: ['adam@acme.com'],
        subject: 'Mobile launch: July 22 — no pipeline impact expected',
        body: 'The two-week slip comes from the push-notification provider migration Marcus flagged in May. Nothing sales-facing changes: demo environments stay on web, and the three enterprise deals waiting on mobile all close after July 22 anyway…',
      },
    },
  },
  {
    id: 's-meeting',
    title: 'Thursday planning prep',
    group: 'Yesterday',
    model: 'llama-4-scout',
    cost: 0.0018,
    skill: null,
    awaitingReview: null,
    messages: [
      { role: 'user', text: '/meeting-prep Thursday planning — main topic is the Q3 roadmap tradeoffs' },
      { role: 'tool', name: 'Calendar', input: { query: 'Thursday planning' }, output: 'Found: "Product Planning" — Thu Jun 11, 10:00–11:00 AM. Attendees: Adam, Marcus Webb, Priya Nair, Sarah Chen, Tom Okafor.' },
      { role: 'tool', name: 'RecallMemory', input: { query: 'Q3 roadmap decisions' }, output: 'Related: "Deferred offline mode to Q3" (May 28), "Onboarding funnel baseline" (Jun 6).' },
      { role: 'assistant', text: 'Agenda for Thursday, built around the tradeoff you actually need to resolve:\n\n**Product Planning — Thu 10:00, 60 min**\n\n1. **Q2 status** (5 min) — mobile launch now July 22; brief, no discussion\n2. **The Q3 fork** (35 min) — we can staff *one* of: offline mode (committed in May) or onboarding checklist (new, backed by funnel data). Decision owner: you\n3. **Pre-reads** — funnel baseline memo, offline deferral decision log\n4. **Parking lot** (10 min) — v2.4 release notes owner, design crit cadence\n\nTalking point for the fork: offline was promised to 2 enterprise accounts; the checklist projects +6pp activation. One slide each, then decide in the room.\n\nThe agenda doc is drafted — want me to send invites with it attached?' },
    ],
  },
  {
    id: 's-notes',
    title: 'Release notes v2.4',
    group: 'This week',
    model: 'gemini-3-pro',
    cost: 0.0127,
    skill: null,
    awaitingReview: null,
    messages: [
      { role: 'user', text: '/release-notes v2.4 — pull from the merged PRs since v2.3' },
      { role: 'tool', name: 'QueryTickets', input: { project: 'core', since: 'v2.3' }, output: '23 merged: 9 features, 11 fixes, 3 internal. Top: bulk export (CORE-1182), comment threading (CORE-1190), faster search indexing (CORE-1201).' },
      { role: 'assistant', text: 'Drafted in three voices — pick one and I\u2019ll finish the set:\n\n**1. Plain** — "You can now export multiple docs at once. Select them in the list view and choose Export."\n\n**2. Benefit-led** — "Stop exporting one doc at a time. Bulk export ships today: select, export, done."\n\n**3. Changelog-terse** — "Added: bulk export from list view (CORE-1182)."\n\nThe full draft with all 9 features in voice 2 is saved locally as *Release Notes — v2.4 (draft)*.' },
      { role: 'user', text: 'Voice 2. Tighten the fixes section to one line each.' },
      { role: 'assistant', text: 'Done — fixes are now single lines, grouped under "Also fixed." The draft is updated in your Documents. Two flags:\n\n- CORE-1190 (comment threading) ships behind a flag — I marked it "rolling out gradually"\n- The search-indexing change is internal; I left it out of the public notes' },
    ],
  },
  {
    id: 's-sarah',
    title: 'What do we know about Sarah?',
    group: 'This week',
    model: 'llama-4-scout',
    cost: 0.0009,
    skill: null,
    awaitingReview: null,
    messages: [
      { role: 'user', text: 'what do you know about Sarah?' },
      { role: 'tool', name: 'SearchMemories', input: { query: 'Sarah' }, output: '1 match: "Sarah Chen — VP Sales" (stakeholder), updated Jun 8.' },
      { role: 'assistant', text: 'From memory:\n\n**Sarah Chen — VP Sales.** Reads updates on her phone; keep them under 200 words with revenue impact in the first line. Concrete language only. Sends questions on Slack and expects same-day answers. She backs the mobile launch but is watching the Q2 slippage closely — updates land best on Tuesdays.' },
    ],
  },
];

// ── Canned response for the live streaming simulation ───────────────────────
const PM_SIM_RESPONSE = {
  tool: { name: 'RecallMemory', input: { query: 'related context' }, output: 'Searched 9 memories — 2 related: "Q2 mobile launch — scope", "Onboarding funnel baseline".' },
  text: 'Good question — here\u2019s where I\u2019d start.\n\nBased on what\u2019s in memory, the two threads that matter are the **July 22 mobile launch** and the **onboarding checklist work** competing for Q3 staffing. If this is for Thursday\u2019s planning meeting, I can pull the funnel baseline and the offline-mode decision log into a one-page pre-read.\n\nWant me to draft that, or dig into something more specific?',
};

const PM_SIM_GREETING_RESPONSES = [
  'On it. Give me a second to pull the relevant context together…',
];

// helper: short model name
function pmModelName(model) {
  if (!model) return null;
  if (model.includes('llama-4-scout')) return 'Scout';
  if (model.startsWith('gemini-3-pro')) return 'Gemini 3 Pro';
  if (model.startsWith('gemini')) return 'Gemini';
  return model;
}
function pmModelHeavy(model) {
  return !!model && !model.includes('llama-4-scout');
}

Object.assign(window, {
  PM_COMMANDS, PM_SKILL_SHORTCUTS, PM_PROVIDERS, PM_INTEGRATIONS, PM_SEARCH_PROVIDERS,
  PM_MEMORY_TYPES, PM_MEMORIES, PM_DOCUMENTS, PM_SESSIONS,
  PM_SIM_RESPONSE, PM_SIM_GREETING_RESPONSES,
  pmModelName, pmModelHeavy,
});
