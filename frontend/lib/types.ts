export interface SessionMetadata {
  active_skill?: string;
  active_skill_phase?: string;
  pending_deliverable?: {
    deliverable_kind?: string;
    document_id?: string;
    summary_for_user?: string;
    url?: string | null;
  };
  pending_action?: PendingAction;
  [key: string]: unknown;
}

export interface SendEmailPreview {
  to: string[];
  cc: string[];
  subject: string;
  body_snippet: string;
}

export interface CreateEventPreview {
  summary: string;
  start_iso: string;
  end_iso: string;
  attendees: string[];
  location?: string;
  description?: string;
}

export type PendingActionKind = "send_email" | "create_event";

export interface PendingAction {
  kind: PendingActionKind;
  tool_name: string;
  params: Record<string, unknown>;
  preview: SendEmailPreview | CreateEventPreview;
  staged_at: string;
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
  /** Client-only: set on an optimistic local message whose send failed, so the
   * UI can mark it and offer a retry. Never present on backend messages. */
  send_failed?: boolean;
}

export interface SessionDetail extends Session {
  messages: Message[];
}

export type WsInbound =
  | {
      type: "session.message";
      session_id: string;
      content: string;
      // Attachment ids from POST /chat/attachments (docs attached to this message).
      attachment_ids?: string[];
    }
  | { type: "session.cancel"; session_id: string };

export type AwaitingReviewKind = "deliverable" | PendingActionKind;

export interface AwaitingReview {
  /** Discriminator: 'deliverable' for skill outputs, 'send_email' / 'create_event' for staged actions. */
  kind: AwaitingReviewKind;
  deliverable_kind: string;
  document_id: string | null;
  summary_for_user: string;
  /** When the deliverable lives in Google Docs, a direct "Open in Google Docs" URL. */
  url?: string | null;
  /** Populated when kind is 'send_email' or 'create_event'. */
  pending_action?: PendingAction | null;
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
      pending_action?: PendingAction | null;
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
  | { type: "session.renamed"; session_id: string; title: string }
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

export interface ScheduleSpec {
  kind: "daily" | "weekdays" | "weekly" | "every_n_hours";
  time?: string; // "HH:MM" local wall clock (daily/weekdays/weekly)
  weekday?: number; // 0=Monday (weekly)
  every_hours?: number; // every_n_hours
}

export interface ScheduledTaskRecord {
  id: string;
  name: string;
  prompt: string;
  schedule: ScheduleSpec;
  enabled: boolean;
  catch_up_missed: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string | null;
  last_session_id: string | null;
  created_at: string;
}
