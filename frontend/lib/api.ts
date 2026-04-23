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
};

export interface GoogleStatus {
  provider: string;
  status: "connected" | "disconnected" | "error";
  connected_at: string | null;
  google_email: string | null;
}
