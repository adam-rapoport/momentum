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
    version: "0.3.8",
    date: "September 25, 2026",
    title: "Claude Opus 5.5 and two more GPT-6 models join the picker",
    highlights: [
      "Claude Opus 5.5 — Anthropic's newest Opus, out this week — is available on your Anthropic key or via OpenRouter. It's better than Opus 5 at multi-step coding and long agent runs, and it's the first Opus that costs less than the one before it: $4 per million words in and $20 out, down from $5 and $25. If you were using Opus 5, 5.5 is a straight upgrade for less money.",
      "GPT-6 Luna and GPT-6 Sol fill in the rest of OpenAI's new generation, on your OpenAI key or via OpenRouter. Luna is now the cheapest model in the whole picker at $0.10 in and $0.50 out — half the price of GPT-5.6 Luna — and Sol gives you GPT-6 quality for a fraction of Astra's price, at $2 and $10. If you use OpenRouter, this is the first time you've had a cheap OpenAI option since the original GPT-5 family was retired in August.",
      "Grok 4.7 joins via OpenRouter, xAI's newer frontier model. Its headline rate is 20% below Grok 4.6, but be aware xAI now attaches a much larger hidden prompt to every turn, so a short turn can actually cost more than it did on 4.6 — Momentum's cost estimate reflects what you're really billed. Grok 4.6 stays in the picker alongside it.",
      "Nothing was removed this time: every model in your picker is still running at its provider.",
      "Cost estimates refreshed on OpenRouter's open models, where the rate follows whichever reseller OpenRouter is routing to that week: GLM 5.3 Flash is half what it was, DeepSeek V4 Pro is down by roughly half, DeepSeek V4 Flash is cheaper to send and dearer to receive, and Kimi K3 and GLM 5.2 went back up. Google, OpenAI, Anthropic, Mistral and Groq prices were all re-checked against their official pages and are unchanged.",
    ],
  },
  {
    version: "0.3.7",
    date: "September 18, 2026",
    title: "Qwen3.6 27B removed — Groq shut it down",
    highlights: [
      "Groq switched off Qwen3.6 27B without notice, so it's been removed from the picker. If you had it selected, Momentum now quietly falls back to another model you have set up — there's nothing you need to do, and no more failed turns. Qwen3.8 27B, its direct successor, is still there and is the natural replacement.",
      "Cost estimates refreshed. GLM 5.2 is now roughly half what it was, GLM 5.3 Flash and DeepSeek V4 Flash got a little cheaper, and Kimi K3 came down again. DeepSeek V4 Pro went up slightly. These are OpenRouter's own rates moving around, not a change to what Momentum charges — it charges nothing.",
      "Every other provider was re-checked against its live catalogue and official price list: Google, OpenAI, Anthropic, Mistral and the rest of Groq are all unchanged.",
    ],
  },
  {
    version: "0.3.6",
    date: "September 11, 2026",
    title: "GPT-6 Astra joins the picker",
    highlights: [
      "GPT-6 Astra — OpenAI's new flagship generation — is available on your OpenAI key or via OpenRouter. It's built for long, multi-step work like deep research, big refactors and long documents. It's the priciest model on the list at $10 per million words in and $50 out, so it's a heavy-slot pick for when you want the best, not an everyday one.",
      "If you use OpenRouter, this is the first OpenAI model back in your picker since the original GPT-5 family was retired in August.",
      "DeepSeek V4.1 Flash joins via OpenRouter — DeepSeek's newest cheap, fast model, built on a new architecture that handles long context better than V4 Flash. Still very inexpensive, and V4 Flash stays in the picker alongside it.",
      "Qwen3.8 Max now points at Alibaba's dated build of the same model. OpenRouter stopped listing the old name, so Momentum switched to the one it still publishes — same model, same price, nothing to do on your end.",
      "Cost estimates refreshed: Kimi K3 and DeepSeek V4 Pro are meaningfully cheaper, and GLM 5.3 Flash's estimate was corrected upward — it had been showing a discounted bulk rate rather than the price a normal turn actually pays. Every other provider's prices were re-checked and are unchanged.",
    ],
  },
  {
    version: "0.3.5",
    date: "September 4, 2026",
    title: "Gemini 3.8 Flash and Claude Fable 5.1 join the picker",
    highlights: [
      "Gemini 3.8 Flash — Google's newest and smartest fast model, released this week — is available on your Google key or via OpenRouter. It's a solid step up from 3.7 Flash on coding and multi-step work, and it costs exactly the same: half price through the end of the year, free tier included.",
      "Claude Fable 5.1 joins on your Anthropic key or via OpenRouter. It's better than Fable 5 at long refactors and long-running work, at the same price — so if you were already using Fable 5, 5.1 is a straight upgrade.",
      "Qwen3.8 27B is now available on Groq, the newer build of the Qwen3.6 27B already in your picker.",
      "No models were removed this time: everything already in your picker is still running at its provider.",
      "Cost estimates refreshed for the OpenRouter models — Llama 3.3 70B is dramatically cheaper and DeepSeek V4 Flash slightly cheaper, while DeepSeek V4 Pro got pricier and GLM 5.2 a little cheaper. Every other provider's prices were re-checked and are unchanged.",
    ],
  },
  {
    version: "0.3.4",
    date: "August 28, 2026",
    title: "Two very cheap new models: Qwen3.8 Flash & GLM 5.3 Flash",
    highlights: [
      "GLM 5.3 Flash joins the picker via OpenRouter — the fast, budget version of GLM 5.3, at roughly a twentieth of its price. It handles coding and long agent runs well, and it's now the cheapest capable model on the list.",
      "Qwen3.8 Flash also joins via OpenRouter — Alibaba's fast Qwen3.8 with a 1M-token context window, at a fraction of Qwen3.8 Max's price. A good everyday pick if you'd rather not spend much.",
      "No models were removed this time: everything already in your picker is still running at its provider.",
      "Cost estimates refreshed for the OpenRouter models — DeepSeek V4 Pro and DeepSeek V4 Flash got cheaper, Llama 3.3 70B and GLM 5.2 got pricier. Every other provider's prices were re-checked and are unchanged.",
    ],
  },
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
