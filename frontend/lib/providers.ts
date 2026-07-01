// Provider metadata for the Connections UI (C8). Only providers that actually
// work today are listed — no "coming soon" stubs. "Google" here is the Google
// AI Studio key (Gemini/Gemma), which is separate from the Google OAuth
// integration (Docs/Gmail/Calendar).
import type { KeyProvider } from "./api";

export type Tier = "light" | "heavy";

export interface ProviderMeta {
  id: string; // UI id
  credProvider: KeyProvider; // backend connection provider string
  name: string;
  tiers: Tier[]; // which model slots this provider can fill (light, heavy, or both)
  pricing: string;
  description: string;
  helpUrl: string;
  helpText: string;
  keyHint: string;
  keyPrefix: string;
  keyLength: [number, number];
  defaultModel: Partial<Record<Tier, string>>; // model auto-selected per slot when this provider is chosen
  // false → the "key" isn't a secret (Ollama's server URL): plain-text input,
  // no Show/Hide, no encryption note. Default true.
  secret?: boolean;
  // Label for the credential input when it isn't an API key (e.g. "Server URL").
  inputLabel?: string;
}

export const PROVIDERS: Record<string, ProviderMeta> = {
  groq: {
    id: "groq",
    credProvider: "llm:groq",
    name: "Groq",
    tiers: ["light", "heavy"],
    pricing: "Free up to 14,400 requests/day · no credit card",
    description: "Fast, free model for routine work. Great default to start with.",
    helpUrl: "https://console.groq.com/keys",
    helpText: 'Sign in at console.groq.com, then "Create API Key".',
    keyHint: "Starts with gsk_, ~56 chars",
    keyPrefix: "gsk_",
    keyLength: [40, 100],
    // Free-tier defaults: gpt-oss-* need a PAID Groq developer tier, so the
    // free Llama models are the defaults (8B light, 70B heavy).
    defaultModel: {
      light: "llama-3.1-8b-instant",
      heavy: "llama-3.3-70b-versatile",
    },
  },
  google: {
    id: "google",
    credProvider: "llm:google_ai",
    name: "Google Gemini",
    tiers: ["light", "heavy"],
    pricing: "Free tier available · paid tier unlocks higher limits",
    description: "Capable reasoning model (Gemini & Gemma) on a generous free tier.",
    helpUrl: "https://aistudio.google.com/apikey",
    helpText: 'In Google AI Studio → "Get API key" → create.',
    keyHint: "Starts with AIza, ~39 chars",
    keyPrefix: "AIza",
    keyLength: [35, 50],
    defaultModel: { light: "gemini-3.5-flash", heavy: "gemini-3.5-flash" },
  },
  openai: {
    id: "openai",
    credProvider: "llm:openai",
    name: "OpenAI",
    tiers: ["light", "heavy"],
    pricing: "Paid · billing required on your OpenAI account",
    description: "The GPT-5 family — nano, mini, GPT-5, and Pro. Paid; works as a light or heavy model.",
    helpUrl: "https://platform.openai.com/api-keys",
    helpText: 'In OpenAI → API keys → "Create new secret key".',
    keyHint: "Starts with sk-",
    keyPrefix: "sk-",
    keyLength: [20, 200],
    defaultModel: { light: "gpt-5-mini", heavy: "gpt-5" },
  },
  anthropic: {
    id: "anthropic",
    credProvider: "llm:anthropic",
    name: "Anthropic Claude",
    tiers: ["light", "heavy"],
    pricing: "Paid · $1–$25 per million tokens by model",
    description: "Claude Haiku, Sonnet, and Opus — strong drafting and reasoning. Paid.",
    helpUrl: "https://console.anthropic.com/settings/keys",
    helpText: 'In the Anthropic Console → API keys → "Create key".',
    keyHint: "Starts with sk-ant-",
    keyPrefix: "sk-ant-",
    keyLength: [40, 200],
    defaultModel: { light: "claude-haiku-4-5", heavy: "claude-sonnet-5" },
  },
  openrouter: {
    id: "openrouter",
    credProvider: "llm:openrouter",
    name: "OpenRouter",
    tiers: ["light", "heavy"],
    pricing: "Pay-as-you-go · one key, many labs",
    description: "An aggregator: one key unlocks models from OpenAI, Google, Anthropic, and more.",
    helpUrl: "https://openrouter.ai/settings/keys",
    helpText: "Sign in at openrouter.ai → Keys → create a key (add credits to use paid models).",
    keyHint: "Starts with sk-or-",
    keyPrefix: "sk-or-",
    keyLength: [30, 200],
    defaultModel: { light: "openai/gpt-5-mini", heavy: "anthropic/claude-sonnet-5" },
  },
  mistral: {
    id: "mistral",
    credProvider: "llm:mistral",
    name: "Mistral",
    tiers: ["light", "heavy"],
    pricing: "Free tier available · paid tier for higher limits",
    description: "Mistral's hosted models — fast, with a usable free tier.",
    helpUrl: "https://console.mistral.ai/api-keys/",
    helpText: "In the Mistral console → API keys → create a key.",
    keyHint: "~32 characters",
    keyPrefix: "",
    keyLength: [20, 80],
    defaultModel: { light: "mistral-small-latest", heavy: "mistral-large-latest" },
  },
  ollama: {
    id: "ollama",
    credProvider: "llm:ollama",
    name: "Ollama (local)",
    tiers: ["light", "heavy"],
    pricing: "Free · runs on this Mac",
    description:
      "Run open models locally — private and free. Tool-capable models (Llama 3.1+, Qwen 2.5+, Mistral-Nemo) are recommended.",
    helpUrl: "https://ollama.com/download",
    helpText:
      "Install Ollama, then run `ollama pull llama3.1:8b` in Terminal. The default address below works for a standard install.",
    keyHint: "e.g. http://localhost:11434",
    keyPrefix: "http",
    keyLength: [10, 200],
    defaultModel: {},
    secret: false,
    inputLabel: "Server URL",
  },
};

export function providersForTier(tier: Tier): ProviderMeta[] {
  return Object.values(PROVIDERS).filter((p) => p.tiers.includes(tier));
}

// Search providers (for the Web Search connection). Same key-card shape as
// model providers, minus the model defaulting.
export interface SearchProviderMeta {
  id: string;
  credProvider: KeyProvider;
  name: string;
  pricing: string;
  description: string;
  helpUrl: string;
  helpText: string;
  keyHint: string;
  keyPrefix: string;
  keyLength: [number, number];
}

export const SEARCH_PROVIDERS: Record<string, SearchProviderMeta> = {
  tavily: {
    id: "tavily",
    credProvider: "search:tavily",
    name: "Tavily",
    pricing: "Free up to 1,000 searches/month",
    description: "Search built for LLMs — clean snippets, no HTML scraping.",
    helpUrl: "https://app.tavily.com",
    helpText: "Sign in at app.tavily.com → copy your API key.",
    keyHint: "Starts with tvly-",
    keyPrefix: "tvly-",
    keyLength: [20, 80],
  },
  perplexity: {
    id: "perplexity",
    credProvider: "search:perplexity",
    name: "Perplexity",
    pricing: "Billed per request by Perplexity",
    description: "Answer-style search with citations, via Perplexity's Sonar API.",
    helpUrl: "https://www.perplexity.ai/settings/api",
    helpText: "In Perplexity → Settings → API → generate a key.",
    keyHint: "Starts with pplx-",
    keyPrefix: "pplx-",
    keyLength: [20, 80],
  },
};

export type ValidationState = "idle" | "partial" | "invalid" | "valid";

export interface FormatValidation {
  state: ValidationState;
  message: string;
}

// Shared shape for anything with a pasteable key (model + search providers).
export interface KeyFormatMeta {
  name: string;
  keyPrefix: string;
  keyHint: string;
  keyLength: [number, number];
  helpUrl: string;
  helpText: string;
  secret?: boolean; // false → plain-text credential (a URL, not a key)
  inputLabel?: string;
}

// Client-side format check — fast feedback as the user types. The real
// provider ping happens on save via the backend validate endpoint.
export function validateKeyFormat(
  provider: KeyFormatMeta | null,
  value: string,
): FormatValidation {
  if (!provider) return { state: "idle", message: "" };
  const v = value.trim();
  if (!v) return { state: "idle", message: "" };
  if (provider.keyPrefix && !v.startsWith(provider.keyPrefix)) {
    return { state: "invalid", message: `Should start with "${provider.keyPrefix}".` };
  }
  const [min, max] = provider.keyLength;
  if (v.length < min) return { state: "partial", message: `${v.length}/${min}+ characters` };
  if (v.length > max) return { state: "invalid", message: `Too long (${v.length} chars).` };
  return { state: "valid", message: "Format looks right." };
}
