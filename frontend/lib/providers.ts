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
  tier: Tier; // which model slot this provider fills in the wizard
  badge?: string;
  badgeKind?: "success" | "default";
  pricing: string;
  description: string;
  helpUrl: string;
  helpText: string;
  keyHint: string;
  keyPrefix: string;
  keyLength: [number, number];
  defaultModel: string; // exact model auto-selected when this provider is chosen
  wizard?: boolean; // show in the first-run wizard? Defaults to true. Paid
                    // providers (OpenAI) stay false — Settings-only — so the
                    // free first-run flow isn't cluttered with billing.
}

export const PROVIDERS: Record<string, ProviderMeta> = {
  groq: {
    id: "groq",
    credProvider: "llm:groq",
    name: "Groq",
    tier: "light",
    badge: "Free",
    badgeKind: "success",
    pricing: "Free up to 14,400 requests/day · no credit card",
    description: "Fast, free model for routine work. Great default to start with.",
    helpUrl: "https://console.groq.com/keys",
    helpText: 'Sign in at console.groq.com, then "Create API Key".',
    keyHint: "Starts with gsk_, ~56 chars",
    keyPrefix: "gsk_",
    keyLength: [40, 100],
    defaultModel: "meta-llama/llama-4-scout-17b-16e-instruct",
  },
  google: {
    id: "google",
    credProvider: "llm:google_ai",
    name: "Google Gemini",
    tier: "heavy",
    badge: "Free tier",
    badgeKind: "success",
    pricing: "Free tier available · paid tier unlocks higher limits",
    description: "Capable reasoning model (Gemini & Gemma) on a generous free tier.",
    helpUrl: "https://aistudio.google.com/apikey",
    helpText: 'In Google AI Studio → "Get API key" → create.',
    keyHint: "Starts with AIza, ~39 chars",
    keyPrefix: "AIza",
    keyLength: [35, 50],
    defaultModel: "gemma-4-31b-it",
  },
  openai: {
    id: "openai",
    credProvider: "llm:openai",
    name: "OpenAI",
    tier: "heavy",
    badge: "Paid",
    badgeKind: "default",
    pricing: "Paid · billing required on your OpenAI account",
    description: "GPT-4o and friends. Optional — adds OpenAI's models alongside your free providers.",
    helpUrl: "https://platform.openai.com/api-keys",
    helpText: 'In OpenAI → API keys → "Create new secret key".',
    keyHint: "Starts with sk-",
    keyPrefix: "sk-",
    keyLength: [20, 200],
    defaultModel: "gpt-4o",
    wizard: false, // Settings-only; keep the free first-run flow uncluttered.
  },
};

export function providersForTier(tier: Tier): ProviderMeta[] {
  // `wizard: false` providers (paid extras) are excluded from the first-run
  // wizard but still usable from Settings.
  return Object.values(PROVIDERS).filter((p) => p.tier === tier && p.wizard !== false);
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
