// Curated release notes for the Settings → "What's new" pane. Newest first.
// Release checklist: add the new version's entry here BEFORE tagging the
// release — the pane and the post-update notice both read from this file.
// Keep the voice plain-English and user-facing (what changed for THEM),
// matching the GitHub release notes but condensed.

export interface ChangelogEntry {
  version: string;
  date: string;
  title: string;
  highlights: string[];
}

export const CHANGELOG: ChangelogEntry[] = [
  {
    version: "0.2.0",
    date: "July 10, 2026",
    title: "20 new PM skills",
    highlights: [
      "The skill library triples: 10 → 30 guided workflows, each invoked with a slash command or just by asking naturally.",
      "Planning & delivery: /roadmap-update, /sprint-planning.",
      "Strategy & growth: /product-strategy, /okr-planning, /launch-plan, /metrics-review, /growth-audit, /opportunity-assessment, /product-vision.",
      "Discovery & go-to-market: /discovery-interview-kit, /positioning-messaging, /pricing-packaging, /experiment-brief.",
      "AI-era PM: /eval-plan, /prototype-brief, /model-selection, /pre-mortem, /prompt-pack, /ai-landscape.",
      "Every new skill passed a line-by-line fact-checking gate against a ground-truth test workspace before shipping.",
    ],
  },
  {
    version: "0.1.2",
    date: "July 7, 2026",
    title: "API key hotfix",
    highlights: [
      "New-format Google API keys are no longer rejected during onboarding or in Settings.",
      "Key-format checks are now advisory for every provider — an unfamiliar format gets verified on save instead of blocking the button. Live key verification is unchanged.",
    ],
  },
  {
    version: "0.1.1",
    date: "July 5, 2026",
    title: "First public release 🎉",
    highlights: [
      "Momentum's debut: an AI agent for product management work that runs entirely on your Mac — no account, no server, no telemetry.",
      "10 built-in PM skills with grounding rules that keep numbers, dates, and quotes honest.",
      "Bring your own model: Google, OpenAI, Anthropic, Groq, OpenRouter, Mistral, or a local Ollama server — keys stored encrypted on your Mac.",
      "Persistent local memory of your stakeholders, decisions, and lessons, plus built-in web search (Tavily or Perplexity).",
      "Signed and notarized installers for Apple Silicon and Intel, with ask-first auto-updates from this release onward.",
    ],
  },
];
