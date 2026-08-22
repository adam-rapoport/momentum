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
    version: "0.3.3",
    date: "August 22, 2026",
    title: "Model refresh: Gemini 3.7 Flash, DeepSeek V4 Pro, GLM 5.3 & more",
    highlights: [
      "Gemini 3.7 Flash — Google's strongest fast model, free tier included — joins the picker (Google or OpenRouter) and becomes the default heavy model for new setups. Gemini 3.5 Flash Lite joins as the new default light model.",
      "New via OpenRouter: DeepSeek V4 Pro, GLM 5.3, Qwen3.8 Max, Grok 4.6, and Meta's Muse Spark 1.2 (Muse needs a one-time 18+ confirmation in your OpenRouter settings). DeepSeek V4 Flash was upgraded to its newest build.",
      "Removed models that stopped working: Groq shut down its two Llama models on August 16 — if one was selected, Momentum now falls back automatically. Also retired: OpenAI's original GPT-5 family (OpenAI ends it in December; GPT-5.4 and 5.6 remain), DeepSeek V3.1/R1, and GLM 5.",
      "Prices refreshed everywhere: Claude Sonnet 5's launch price ($2/$10) is now permanent, the GPT-5.6 family got big cuts (Luna −80%), and Gemini 3.6 Flash halved. Groq's surviving models now work on its free tier (though the free tier stays tight for this app).",
    ],
  },
  {
    version: "0.3.2",
    date: "July 29, 2026",
    title: "New models: GPT-5.4/5.5/5.6, Kimi K3 & Claude Fable 5",
    highlights: [
      "OpenAI's newest generations join the picker: GPT-5.4 (plus mini and nano), GPT-5.5, and the GPT-5.6 trio — Luna (fast), Terra (balanced), and Sol (flagship). All on your OpenAI key.",
      "Claude Fable 5 — Anthropic's new top model tier, above Opus — is available via Anthropic or OpenRouter.",
      "Kimi K3 — Moonshot's flagship, with a 1M-token context window — is available via OpenRouter.",
      "As always, every model can serve either the everyday or the heavy-drafting slot; the labels are just suggestions.",
    ],
  },
  {
    version: "0.3.1",
    date: "July 24, 2026",
    title: "New models: Gemini 3.6 Flash & Claude Opus 5",
    highlights: [
      "Gemini 3.6 Flash — Google's newest fast model, with a free tier — is available in the model picker, via Google or OpenRouter.",
      "Claude Opus 5 — Anthropic's most capable model — joins the picker too, via Anthropic or OpenRouter, at the same price as Opus 4.8.",
      "Long Claude answers no longer risk getting cut off mid-thought.",
      "Cost estimates refreshed against every provider's current price list, so the per-session cost display is accurate again.",
      "Qwen3 32B was retired from the picker — Groq shut it down upstream; Qwen 3.6 27B is its successor and remains available.",
    ],
  },
  {
    version: "0.3.0",
    date: "July 11, 2026",
    title: "Scheduled tasks, exports & a menu-bar home",
    highlights: [
      "Scheduled tasks: save a prompt and a schedule — a morning briefing, a weekly digest — and Momentum runs it automatically, dropping results into your chat list marked ⏰. Skills work too, and anything send-like still waits for your approval.",
      "Momentum now lives in your menu bar: closing the window keeps it running quietly (that's how scheduled tasks fire), and the Dock icon or the ≫ menu-bar icon brings it back. ⌘Q still quits completely.",
      "Export any document as Word or PDF from the Documents panel — headings, tables, lists, and links all carry over.",
      "Upload PowerPoint decks, Excel sheets, and CSV files everywhere you could already upload documents.",
      "Check for updates any time from the menu-bar icon — and with the app running long-term, it now re-checks on its own every few hours.",
      "This What's new panel: after each update, a one-time notice shows you what changed.",
    ],
  },
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
