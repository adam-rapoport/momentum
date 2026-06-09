import { getBackendToken } from "./desktop";
import type {
  DocumentArtifact,
  MemoryRecordDetail,
  MemoryRecordSummary,
  Session,
  SessionDetail,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Desktop builds authenticate every API call with the shell's per-launch
  // token; in web dev this resolves to null and no header is sent.
  const token = await getBackendToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-PMomentum-Token": token } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    // FastAPI returns errors as {"detail": "..."} — surface that human-readable
    // message rather than the raw JSON blob.
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // not JSON; keep the raw text
    }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listSessions: () => request<Session[]>("/api/v1/sessions"),
  getSession: (id: string) => request<SessionDetail>(`/api/v1/sessions/${id}`),
  createSession: (body: { title?: string }) =>
    request<Session>("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateSession: (id: string, body: { title?: string; status?: string }) =>
    request<Session>(`/api/v1/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  archiveSession: (id: string) =>
    request<void>(`/api/v1/sessions/${id}`, { method: "DELETE" }),

  listMemories: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return request<MemoryRecordSummary[]>(`/api/v1/memory${q}`);
  },
  getMemory: (id: string) =>
    request<MemoryRecordDetail>(`/api/v1/memory/${id}`),

  listDocuments: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return request<DocumentArtifact[]>(`/api/v1/documents${q}`);
  },

  googleStatus: () =>
    request<GoogleStatus>(`/api/v1/integrations/google/status`),
  googleConnect: () =>
    request<{ authorize_url: string }>(`/api/v1/integrations/google/connect`, {
      method: "POST",
    }),
  googleDisconnect: () =>
    request<void>(`/api/v1/integrations/google`, { method: "DELETE" }),

  getModelPreferences: () =>
    request<ModelPreferences>(`/api/v1/preferences/models`),
  setModelPreferences: (body: ModelPreferencesUpdate) =>
    request<ModelPreferences>(`/api/v1/preferences/models`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // ── C8 Connections (provider API keys) ──
  listConnections: () =>
    request<{ connections: ConnectionStatus[] }>(`/api/v1/connections`),
  validateConnection: (provider: string, apiKey: string) =>
    request<{ ok: boolean; detail: string }>(
      `/api/v1/connections/${encodeURIComponent(provider)}/validate`,
      { method: "POST", body: JSON.stringify({ api_key: apiKey }) },
    ),
  setConnection: (provider: string, apiKey: string) =>
    request<{ detail: string; connection: ConnectionStatus }>(
      `/api/v1/connections/${encodeURIComponent(provider)}`,
      { method: "PUT", body: JSON.stringify({ api_key: apiKey }) },
    ),
  deleteConnection: (provider: string) =>
    request<void>(`/api/v1/connections/${encodeURIComponent(provider)}`, {
      method: "DELETE",
    }),

  // ── C8 Onboarding ──
  onboardingStatus: () =>
    request<OnboardingStatus>(`/api/v1/onboarding/status`),
  completeOnboarding: () =>
    request<{ completed_at: string }>(`/api/v1/onboarding/complete`, {
      method: "POST",
    }),
  saveProfile: (body: { role?: string; company?: string; goals?: string }) =>
    request<{ saved: string[] }>(`/api/v1/onboarding/profile`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  uploadDocument: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    // Note: do NOT set Content-Type — the browser sets the multipart boundary.
    const res = await fetch(`${API_BASE}/api/v1/onboarding/documents`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
    }
    return (await res.json()) as {
      title: string;
      memory_id: string;
      char_count: number;
      memories_created: number;
    };
  },

  // ── C8 Web search provider preference ──
  getSearchPreferences: () =>
    request<SearchPreferences>(`/api/v1/preferences/search`),
  setSearchProvider: (provider: "tavily" | "perplexity") =>
    request<{ provider: string }>(`/api/v1/preferences/search`, {
      method: "PUT",
      body: JSON.stringify({ provider }),
    }),

  // ── Slash-command discovery (powers the "/" menu in the chat input) ──
  listCommands: () =>
    request<{ commands: CommandSummary[] }>(`/api/v1/commands`),

  // ── User/workspace name (drives the Sidebar; set during onboarding) ──
  getProfile: () => request<UserProfile>(`/api/v1/preferences/profile`),
  setProfile: (body: { display_name?: string; workspace_name?: string }) =>
    request<UserProfile>(`/api/v1/preferences/profile`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

export interface UserProfile {
  display_name: string | null;
  workspace_name: string | null;
}

export interface CommandSummary {
  command: string; // the token after "/", e.g. "write-prd" or "deep"
  description: string;
  kind: "skill" | "builtin";
}

export interface SearchPreferences {
  provider: "tavily" | "perplexity";
  tavily_configured: boolean;
  perplexity_configured: boolean;
}

export type KeyProvider =
  | "llm:groq"
  | "llm:google_ai"
  | "llm:openai"
  | "search:tavily"
  | "search:perplexity";

export interface ConnectionStatus {
  provider: KeyProvider;
  configured: boolean;
  source: "stored" | "env" | "none";
  key_suffix: string | null;
  status: "connected" | "disconnected" | "error";
  last_validated_at: string | null;
  last_error: string | null;
}

export interface OnboardingStatus {
  configured: boolean;
  has_light_provider: boolean;
  has_heavy_provider: boolean;
  completed_at: string | null;
}

export interface GoogleStatus {
  provider: string;
  status: "connected" | "disconnected" | "error";
  connected_at: string | null;
  google_email: string | null;
  scopes: string[];
  enabled_services: string[]; // subset of ["docs", "gmail", "calendar"]
  needs_reconnect: boolean;   // true when connected but missing new scopes
}

export interface ModelEntry {
  id: string;
  provider: "groq" | "google" | "openai";
  display_name: string;
  role: "light" | "heavy" | "either";
  notes: string;
}

export interface ModelPreferences {
  light_model: string | null;            // user's pick, or null if unset
  heavy_model: string | null;
  effective_light_model: string;         // what would actually be used right now
  effective_heavy_model: string;
  available_light_models: ModelEntry[];
  available_heavy_models: ModelEntry[];
}

export interface ModelPreferencesUpdate {
  light_model?: string | null;           // null/empty clears the pick
  heavy_model?: string | null;
}
