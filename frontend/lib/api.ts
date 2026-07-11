import { getApiBase, getBackendToken } from "./desktop";
import type {
  DocumentArtifact,
  MemoryRecordDetail,
  MemoryRecordSummary,
  Session,
  SessionDetail,
} from "./types";

// Every request gets a deadline. Without one, a wedged backend leaves the
// promise pending forever — and anything awaiting it (the stream.done
// refetch, the boot poll, a panel load) hangs with it. 15s is generous for
// localhost; uploads get longer (the backend runs LLM extraction on them).
const DEFAULT_TIMEOUT_MS = 15_000;
// Uploads wait on a *synchronous* heavy-model extraction pass, and the slower
// models (GPT-5 / GPT-5-Pro and other reasoning models) can take minutes on a
// long doc. The old 120s ceiling made those uploads report a false "failed"
// even though the backend finished and saved the reference + memories. 5
// minutes covers the realistic worst case while keeping the inline
// "N memories created" confirmation.
const UPLOAD_TIMEOUT_MS = 300_000;

function timeoutError(err: unknown, timeoutMs: number): Error | null {
  if (
    err instanceof DOMException &&
    (err.name === "TimeoutError" || err.name === "AbortError")
  ) {
    return new Error(
      `The backend didn't respond within ${Math.round(timeoutMs / 1000)} seconds. It may still be starting, or busy — please try again.`,
    );
  }
  return null;
}

// FastAPI returns errors as {"detail": "..."} — surface that human-readable
// message rather than the raw JSON blob.
function detailFromBody(text: string): string {
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON; keep the raw text
  }
  return text;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  // Desktop builds authenticate every API call with the shell's per-launch
  // token and derive the base URL from the port the shell actually chose;
  // in web dev these resolve to null/the compile-time default.
  const [base, token] = await Promise.all([getApiBase(), getBackendToken()]);
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(timeoutMs),
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Momentum-Token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw timeoutError(err, timeoutMs) ?? err;
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(detailFromBody(text) || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface DocumentUploadResult {
  title: string;
  memory_id: string;
  char_count: number;
  memories_created: number;
}

// Multipart upload to a document-ingestion endpoint. Note: do NOT set
// Content-Type — the browser sets the multipart boundary. The auth header
// still applies (these endpoints are not token-exempt). The long timeout
// covers the backend's heavy-model extraction step.
async function uploadFileTo<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const [base, token] = await Promise.all([getApiBase(), getBackendToken()]);
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
      headers: token ? { "X-Momentum-Token": token } : {},
    });
  } catch (err) {
    throw timeoutError(err, UPLOAD_TIMEOUT_MS) ?? err;
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(detailFromBody(text) || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

// Result of POST /chat/attachments — a doc parsed and cached for the next turn.
export interface ChatAttachmentResult {
  attachment_id: string;
  filename: string;
  char_count: number;
}

export const api = {
  // `q` searches titles AND message contents (server-side); omit for the full
  // list.
  listSessions: (q?: string) =>
    request<Session[]>(
      `/api/v1/sessions${q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`,
    ),
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

  // `q` matches a keyword in a memory's NAME or its CONTENT (server-side, via
  // the search_text index); omit for the full list.
  listMemories: (projectId?: string, q?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", projectId);
    if (q && q.trim()) params.set("q", q.trim());
    const qs = params.toString();
    return request<MemoryRecordSummary[]>(`/api/v1/memory${qs ? `?${qs}` : ""}`);
  },
  getMemory: (id: string) =>
    request<MemoryRecordDetail>(`/api/v1/memory/${id}`),

  listDocuments: (projectId?: string) => {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    return request<DocumentArtifact[]>(`/api/v1/documents${q}`);
  },

  // Desktop export: the backend converts and writes straight to the path the
  // user picked in the native Save dialog.
  exportDocumentToPath: (documentId: string, format: "docx" | "pdf", destPath: string) =>
    request<{ file_path: string }>(`/api/v1/documents/export`, {
      method: "POST",
      body: JSON.stringify({ document_id: documentId, format, dest_path: destPath }),
    }),

  // Web export: no dest_path → the converted bytes come back as a download.
  // Raw fetch because request() JSON-parses every body.
  exportDocumentDownload: async (
    documentId: string,
    format: "docx" | "pdf",
  ): Promise<Blob> => {
    const [base, token] = await Promise.all([getApiBase(), getBackendToken()]);
    let res: Response;
    try {
      res = await fetch(`${base}/api/v1/documents/export`, {
        method: "POST",
        signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "X-Momentum-Token": token } : {}),
        },
        body: JSON.stringify({ document_id: documentId, format }),
      });
    } catch (err) {
      throw timeoutError(err, DEFAULT_TIMEOUT_MS) ?? err;
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(detailFromBody(text) || `${res.status} ${res.statusText}`);
    }
    return res.blob();
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
  // Installed models on the user's local Ollama server (400 until connected).
  listOllamaModels: () =>
    request<{ base_url: string; models: OllamaModel[] }>(
      `/api/v1/connections/ollama/models`,
    ),

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
  uploadDocument: (file: File) =>
    uploadFileTo<DocumentUploadResult>("/api/v1/onboarding/documents", file),
  // Same pipeline, triggered from the Memory panel after onboarding.
  uploadMemoryDocument: (file: File) =>
    uploadFileTo<DocumentUploadResult>("/api/v1/memory/documents", file),
  // Parse + cache a doc to attach to the next chat message (no permanent memory).
  uploadChatAttachment: (file: File) =>
    uploadFileTo<ChatAttachmentResult>("/api/v1/chat/attachments", file),

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
  | "llm:anthropic"
  | "llm:openrouter"
  | "llm:mistral"
  | "llm:ollama"
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
  provider: "groq" | "google" | "openai" | "anthropic" | "openrouter" | "mistral";
  display_name: string;
  role: "light" | "heavy" | "either";
  notes: string;
}

// One installed model on the user's local Ollama server (dynamic — whatever
// they've pulled; ids carry the "ollama:" prefix the backend expects).
export interface OllamaModel {
  id: string;
  name: string;
  supports_tools: boolean;
  context_length: number | null;
}

export interface ModelPreferences {
  light_model: string | null;            // user's pick, or null if unset
  heavy_model: string | null;
  effective_light_model: string;         // what would actually be used right now
  effective_heavy_model: string;
  available_light_models: ModelEntry[];
  available_heavy_models: ModelEntry[];
  // Full registry, unfiltered by configured providers — lets the onboarding
  // wizard offer a model choice before any key is saved.
  registry_models: ModelEntry[];
}

export interface ModelPreferencesUpdate {
  light_model?: string | null;           // null/empty clears the pick
  heavy_model?: string | null;
}
