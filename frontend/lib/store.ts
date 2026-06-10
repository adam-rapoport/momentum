"use client";
import { create } from "zustand";
import type {
  AwaitingReview,
  DocumentArtifact,
  LiveToolCall,
  MemoryRecordSummary,
  Message,
  Session,
} from "./types";

export interface SessionError {
  code: string;
  message: string;
}

interface ChatState {
  sessions: Session[];
  messagesBySession: Record<string, Message[]>;
  streamingBySession: Record<string, string>;
  isStreamingBySession: Record<string, boolean>;
  totalCostBySession: Record<string, string>;
  liveToolCallsBySession: Record<string, LiveToolCall[]>;
  awaitingReviewBySession: Record<string, AwaitingReview>;
  lastErrorBySession: Record<string, SessionError>;
  lastModelBySession: Record<string, string>;
  // Monotonic per-session turn counter, bumped every time a new turn starts
  // streaming. Async work that finishes late (the getSession refetch after
  // stream.done / stream.awaiting_review, the reconnect resync) captures the
  // epoch when it starts and drops its result if a newer turn began since —
  // otherwise a slow refetch from turn N clobbers turn N+1's live state.
  turnEpochBySession: Record<string, number>;
  // True when the most recent turn ended because the user hit Cancel. Cleared
  // when the next turn starts. Drives the small "stopped" note in the chat.
  stoppedBySession: Record<string, boolean>;
  memories: MemoryRecordSummary[];
  memoriesLoadedAt: number;
  documents: DocumentArtifact[];
  documentsLoadedAt: number;
  wsConnected: boolean;
  // The session currently shown on /chat (from the ?s= query param). Tracked in
  // the store so the Sidebar can highlight it without reading search params
  // itself (which would need its own <Suspense> boundary under static export).
  activeSessionId: string | null;

  setSessions: (s: Session[]) => void;
  upsertSession: (s: Session) => void;
  removeSession: (id: string) => void;

  setMessages: (sessionId: string, messages: Message[]) => void;
  appendUserMessage: (sessionId: string, content: string) => void;
  /** Mark the newest optimistic (local-*) user message as failed-to-send. */
  markSendFailed: (sessionId: string) => void;
  removeMessage: (sessionId: string, messageId: string) => void;

  startStreaming: (sessionId: string) => void;
  appendStreamChunk: (sessionId: string, text: string) => void;
  toolStart: (
    sessionId: string,
    args: { call_id: string; name: string; input: Record<string, unknown> },
  ) => void;
  toolResult: (
    sessionId: string,
    args: { call_id: string; output: string; is_error: boolean },
  ) => void;
  /**
   * End the live-streaming state for a turn. `totalCost` undefined preserves
   * the previously displayed cost (error paths must not reset it to $0);
   * `cancelled` true records that the user stopped the turn.
   */
  finalizeStream: (sessionId: string, totalCost?: string, cancelled?: boolean) => void;
  /** Seed/refresh the header cost from a fetched session record, so reopening
   * a session shows its accumulated cost before any new turn completes. */
  setTotalCost: (sessionId: string, totalCost: string) => void;

  setAwaitingReview: (sessionId: string, review: AwaitingReview) => void;
  clearAwaitingReview: (sessionId: string) => void;

  setLastError: (sessionId: string, error: SessionError) => void;
  clearLastError: (sessionId: string) => void;

  setLastModel: (sessionId: string, model: string) => void;

  setMemories: (memories: MemoryRecordSummary[]) => void;
  setDocuments: (documents: DocumentArtifact[]) => void;

  setWsConnected: (connected: boolean) => void;
  setActiveSession: (id: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  messagesBySession: {},
  streamingBySession: {},
  isStreamingBySession: {},
  totalCostBySession: {},
  liveToolCallsBySession: {},
  awaitingReviewBySession: {},
  lastErrorBySession: {},
  lastModelBySession: {},
  turnEpochBySession: {},
  stoppedBySession: {},
  memories: [],
  memoriesLoadedAt: 0,
  documents: [],
  documentsLoadedAt: 0,
  wsConnected: false,
  activeSessionId: null,

  setSessions: (sessions) => set({ sessions }),
  upsertSession: (s) =>
    set((state) => {
      const others = state.sessions.filter((x) => x.id !== s.id);
      return { sessions: [s, ...others] };
    }),
  removeSession: (id) =>
    set((state) => ({ sessions: state.sessions.filter((s) => s.id !== id) })),

  setMessages: (sessionId, messages) =>
    set((state) => ({
      messagesBySession: { ...state.messagesBySession, [sessionId]: messages },
    })),

  appendUserMessage: (sessionId, content) =>
    set((state) => {
      const prev = state.messagesBySession[sessionId] ?? [];
      const lastTurn = prev.length ? prev[prev.length - 1].turn_id : 0;
      const newUser: Message = {
        // randomUUID, not Date.now(): two sends in the same millisecond
        // (e.g. a retry racing a queued flush) must not collide on key.
        id: `local-${crypto.randomUUID()}`,
        turn_id: lastTurn + 1,
        role: "user",
        content: [{ type: "text", text: content }],
        created_at: new Date().toISOString(),
      };
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: [...prev, newUser],
        },
      };
    }),

  markSendFailed: (sessionId) =>
    set((state) => {
      const prev = state.messagesBySession[sessionId] ?? [];
      // Find the newest optimistic user message that hasn't failed yet.
      let idx = -1;
      for (let i = prev.length - 1; i >= 0; i--) {
        const m = prev[i];
        if (m.role === "user" && m.id.startsWith("local-") && !m.send_failed) {
          idx = i;
          break;
        }
      }
      if (idx === -1) return state;
      const next = [...prev];
      next[idx] = { ...next[idx], send_failed: true };
      return {
        messagesBySession: { ...state.messagesBySession, [sessionId]: next },
      };
    }),

  removeMessage: (sessionId, messageId) =>
    set((state) => {
      const prev = state.messagesBySession[sessionId] ?? [];
      const next = prev.filter((m) => m.id !== messageId);
      if (next.length === prev.length) return state;
      return {
        messagesBySession: { ...state.messagesBySession, [sessionId]: next },
      };
    }),

  startStreaming: (sessionId) =>
    set((state) => ({
      streamingBySession: { ...state.streamingBySession, [sessionId]: "" },
      isStreamingBySession: { ...state.isStreamingBySession, [sessionId]: true },
      liveToolCallsBySession: { ...state.liveToolCallsBySession, [sessionId]: [] },
      turnEpochBySession: {
        ...state.turnEpochBySession,
        [sessionId]: (state.turnEpochBySession[sessionId] ?? 0) + 1,
      },
      stoppedBySession: { ...state.stoppedBySession, [sessionId]: false },
    })),

  appendStreamChunk: (sessionId, text) =>
    set((state) => ({
      streamingBySession: {
        ...state.streamingBySession,
        [sessionId]: (state.streamingBySession[sessionId] ?? "") + text,
      },
    })),

  toolStart: (sessionId, { call_id, name, input }) =>
    set((state) => {
      const prev = state.liveToolCallsBySession[sessionId] ?? [];
      const next: LiveToolCall = { call_id, name, input, status: "running" };
      return {
        liveToolCallsBySession: {
          ...state.liveToolCallsBySession,
          [sessionId]: [...prev, next],
        },
      };
    }),

  toolResult: (sessionId, { call_id, output, is_error }) =>
    set((state) => {
      const prev = state.liveToolCallsBySession[sessionId] ?? [];
      return {
        liveToolCallsBySession: {
          ...state.liveToolCallsBySession,
          [sessionId]: prev.map((tc) =>
            tc.call_id === call_id
              ? { ...tc, output, isError: is_error, status: is_error ? "error" : "done" }
              : tc,
          ),
        },
      };
    }),

  // Finalize the streaming turn. We DON'T synthesize an optimistic message
  // here — instead, ChatView refetches session detail so the authoritative
  // content (tool_use + tool_result blocks with real IDs) replaces the
  // live view. This keeps tool pairing consistent.
  finalizeStream: (sessionId, totalCost, cancelled) =>
    set((state) => ({
      streamingBySession: { ...state.streamingBySession, [sessionId]: "" },
      isStreamingBySession: { ...state.isStreamingBySession, [sessionId]: false },
      liveToolCallsBySession: { ...state.liveToolCallsBySession, [sessionId]: [] },
      // Error/cancel paths pass no cost — keep showing the last known value
      // instead of resetting the header to $0.
      totalCostBySession:
        totalCost === undefined
          ? state.totalCostBySession
          : { ...state.totalCostBySession, [sessionId]: totalCost },
      stoppedBySession: cancelled
        ? { ...state.stoppedBySession, [sessionId]: true }
        : state.stoppedBySession,
    })),

  setTotalCost: (sessionId, totalCost) =>
    set((state) => ({
      totalCostBySession: { ...state.totalCostBySession, [sessionId]: totalCost },
    })),

  setAwaitingReview: (sessionId, review) =>
    set((state) => ({
      awaitingReviewBySession: {
        ...state.awaitingReviewBySession,
        [sessionId]: review,
      },
    })),

  clearAwaitingReview: (sessionId) =>
    set((state) => {
      if (!(sessionId in state.awaitingReviewBySession)) return state;
      const next = { ...state.awaitingReviewBySession };
      delete next[sessionId];
      return { awaitingReviewBySession: next };
    }),

  setLastError: (sessionId, error) =>
    set((state) => ({
      lastErrorBySession: { ...state.lastErrorBySession, [sessionId]: error },
    })),

  clearLastError: (sessionId) =>
    set((state) => {
      if (!(sessionId in state.lastErrorBySession)) return state;
      const next = { ...state.lastErrorBySession };
      delete next[sessionId];
      return { lastErrorBySession: next };
    }),

  setLastModel: (sessionId, model) =>
    set((state) => ({
      lastModelBySession: { ...state.lastModelBySession, [sessionId]: model },
    })),

  setMemories: (memories) =>
    set({ memories, memoriesLoadedAt: Date.now() }),

  setDocuments: (documents) =>
    set({ documents, documentsLoadedAt: Date.now() }),

  setWsConnected: (connected) => set({ wsConnected: connected }),
  setActiveSession: (activeSessionId) => set({ activeSessionId }),
}));
