export interface SessionMetadata {
  active_skill?: string;
  active_skill_phase?: string;
  pending_deliverable?: {
    deliverable_kind?: string;
    document_id?: string;
    summary_for_user?: string;
    url?: string | null;
  };
  [key: string]: unknown;
}

export interface Session {
  id: string;
  user_id: string;
  project_id: string;
  title: string | null;
  permission_mode: string;
  llm_provider: string;
  llm_model: string;
  status: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: string;
  turn_count: number;
  session_metadata?: SessionMetadata;
  created_at: string;
  updated_at: string;
}

export interface TextBlock {
  type: "text";
  text: string;
}

export interface ToolUseBlock {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: "tool_result";
  tool_use_id: string;
  tool_name?: string;
  output: string;
  is_error?: boolean;
}

export type ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock;

export interface Message {
  id: string;
  turn_id: number;
  role: "user" | "assistant" | "tool" | "system";
  content: ContentBlock[];
  created_at: string;
}

export interface SessionDetail extends Session {
  messages: Message[];
}

export type WsInbound =
  | { type: "session.message"; session_id: string; content: string }
  | { type: "session.cancel"; session_id: string };

export interface AwaitingReview {
  deliverable_kind: string;
  document_id: string | null;
  summary_for_user: string;
  /** When the deliverable lives in Google Docs, a direct "Open in Google Docs" URL. */
  url?: string | null;
}

export type WsOutbound =
  | { type: "stream.text"; session_id: string; text: string }
  | {
      type: "stream.tool_start";
      session_id: string;
      call_id: string;
      name: string;
      input: Record<string, unknown>;
    }
  | {
      type: "stream.tool_result";
      session_id: string;
      call_id: string;
      name: string;
      output: string;
      is_error: boolean;
    }
  | ({
      type: "stream.awaiting_review";
      session_id: string;
      model?: string | null;
    } & AwaitingReview)
  | {
      type: "stream.done";
      session_id: string;
      usage: {
        input_tokens: number;
        output_tokens: number;
        cost_usd: string;
        total_cost_usd: string;
      };
      metadata: { cancelled: boolean; model?: string | null };
    }
  | { type: "error"; code: string; message: string; session_id?: string };

export interface LiveToolCall {
  call_id: string;
  name: string;
  input: Record<string, unknown>;
  output?: string;
  isError?: boolean;
  status: "running" | "done" | "error";
}

export type MemoryType =
  | "stakeholder"
  | "decision"
  | "product"
  | "team"
  | "lessons"
  | "reference";

export interface MemoryRecordSummary {
  id: string;
  project_id: string;
  type: MemoryType | string;
  title: string;
  slug: string;
  summary: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface MemoryRecordDetail extends MemoryRecordSummary {
  body: string;
  file_path: string;
}

export interface DocumentArtifact {
  document_id: string;
  title: string;
  backend: "google_docs" | "local" | string;
  created_at: string;
  updated_at: string;
  char_count: number;
  url: string | null;
  google_doc_id: string | null;
  file_path: string | null;
}
