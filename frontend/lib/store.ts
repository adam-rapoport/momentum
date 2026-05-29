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
  finalizeStream: (sessionId: string, totalCost: string, cancelled: boolean) => void;

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
        id: `local-${Date.now()}`,
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

  startStreaming: (sessionId) =>
    set((state) => ({
      streamingBySession: { ...state.streamingBySession, [sessionId]: "" },
      isStreamingBySession: { ...state.isStreamingBySession, [sessionId]: true },
      liveToolCallsBySession: { ...state.liveToolCallsBySession, [sessionId]: [] },
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
  finalizeStream: (sessionId, totalCost) =>
    set((state) => ({
      streamingBySession: { ...state.streamingBySession, [sessionId]: "" },
      isStreamingBySession: { ...state.isStreamingBySession, [sessionId]: false },
      liveToolCallsBySession: { ...state.liveToolCallsBySession, [sessionId]: [] },
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
