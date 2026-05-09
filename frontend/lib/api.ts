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
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
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
};

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
  provider: "groq" | "google";
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
