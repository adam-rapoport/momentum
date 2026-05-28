"use client";
import { useEffect, useMemo, useRef } from "react";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { getWsClient } from "@/lib/ws";
import type {
  LiveToolCall,
  Message,
  ToolResultBlock,
} from "@/lib/types";
import { ApprovalBar } from "./ApprovalBar";
import { ChatInput } from "./ChatInput";
import { Banner } from "./connections/kit";
import { MessageBubble, StreamingBubble } from "./MessageBubble";
import { ToolCallBlock } from "./ToolCallBlock";

interface Props {
  sessionId: string;
}

const EMPTY_MESSAGES: Message[] = [];
const EMPTY_TOOLS: LiveToolCall[] = [];

type DisplayItem =
  | {
      kind: "text";
      role: "user" | "assistant";
      text: string;
      key: string;
    }
  | {
      kind: "tool";
      name: string;
      input: Record<string, unknown>;
      output?: string;
      isError?: boolean;
      status: "running" | "done" | "error";
      key: string;
    };

function messagesToItems(messages: Message[]): DisplayItem[] {
  const results = new Map<string, ToolResultBlock>();
  for (const m of messages) {
    if (m.role === "tool") {
      for (const b of m.content) {
        if (b.type === "tool_result") results.set(b.tool_use_id, b);
      }
    }
  }

  const items: DisplayItem[] = [];
  for (const m of messages) {
    if (m.role === "tool") continue;
    m.content.forEach((b, i) => {
      const key = `${m.id}:${i}`;
      if (b.type === "text" && b.text) {
        items.push({
          kind: "text",
          role: m.role === "user" ? "user" : "assistant",
          text: b.text,
          key,
        });
      } else if (b.type === "tool_use") {
        const r = results.get(b.id);
        items.push({
          kind: "tool",
          name: b.name,
          input: b.input,
          output: r?.output,
          isError: !!r?.is_error,
          status: r ? (r.is_error ? "error" : "done") : "running",
          key,
        });
      }
    });
  }
  return items;
}

export function ChatView({ sessionId }: Props) {
  const messages =
    useChatStore((s) => s.messagesBySession[sessionId]) ?? EMPTY_MESSAGES;
  const streaming = useChatStore((s) => s.streamingBySession[sessionId]) ?? "";
  const isStreaming =
    useChatStore((s) => s.isStreamingBySession[sessionId]) ?? false;
  const liveTools =
    useChatStore((s) => s.liveToolCallsBySession[sessionId]) ?? EMPTY_TOOLS;
  const awaitingReview = useChatStore(
    (s) => s.awaitingReviewBySession[sessionId],
  );
  const lastError = useChatStore((s) => s.lastErrorBySession[sessionId]);
  const setMessages = useChatStore((s) => s.setMessages);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const startStreaming = useChatStore((s) => s.startStreaming);
  const upsertSession = useChatStore((s) => s.upsertSession);
  const setAwaitingReview = useChatStore((s) => s.setAwaitingReview);
  const clearAwaitingReview = useChatStore((s) => s.clearAwaitingReview);
  const clearLastError = useChatStore((s) => s.clearLastError);

  const items = useMemo(() => messagesToItems(messages), [messages]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSession(sessionId)
      .then((detail) => {
        if (cancelled) return;
        setMessages(sessionId, detail.messages);
        upsertSession(detail);
        // Rehydrate the pause state after a browser refresh. The backend
        // stores ONE of: pending_action (Chunk E send-side action) or
        // pending_deliverable (skill workflow). Pending action wins if both
        // are somehow set.
        const meta = detail.session_metadata ?? {};
        const pendingAction = meta.pending_action;
        const pendingDeliverable = meta.pending_deliverable;
        if (detail.status === "awaiting_review" && pendingAction) {
          setAwaitingReview(sessionId, {
            kind: pendingAction.kind,
            deliverable_kind: pendingAction.kind,
            document_id: null,
            summary_for_user: "Action staged for approval",
            url: null,
            pending_action: pendingAction,
          });
        } else if (detail.status === "awaiting_review" && pendingDeliverable) {
          setAwaitingReview(sessionId, {
            kind: "deliverable",
            deliverable_kind: String(pendingDeliverable.deliverable_kind ?? ""),
            document_id: pendingDeliverable.document_id
              ? String(pendingDeliverable.document_id)
              : null,
            summary_for_user: String(pendingDeliverable.summary_for_user ?? ""),
            url: pendingDeliverable.url ? String(pendingDeliverable.url) : null,
            pending_action: null,
          });
        } else {
          clearAwaitingReview(sessionId);
        }
      })
      .catch((err) => console.error("failed to load session:", err));
    return () => {
      cancelled = true;
    };
  }, [
    sessionId,
    setMessages,
    upsertSession,
    setAwaitingReview,
    clearAwaitingReview,
  ]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [items.length, streaming, liveTools.length]);

  function handleSend(content: string) {
    // Clear any stale error banner from a previous failed turn so the UI
    // doesn't nag about a message the user is already retrying.
    clearLastError(sessionId);
    appendUserMessage(sessionId, content);
    startStreaming(sessionId);
    getWsClient().send({ type: "session.message", session_id: sessionId, content });
  }

  function handleCancel() {
    getWsClient().send({ type: "session.cancel", session_id: sessionId });
  }

  function handleApprove() {
    clearAwaitingReview(sessionId);
    handleSend("/approve");
  }

  function handleRevise(text: string) {
    clearAwaitingReview(sessionId);
    handleSend(`/revise ${text}`);
  }

  function handleRestart() {
    clearAwaitingReview(sessionId);
    handleSend("/restart");
  }

  const waitingForFirstToken =
    isStreaming && !streaming && liveTools.length === 0;

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-4 space-y-3">
          {items.length === 0 && !isStreaming && (
            <div className="text-center text-sm text-neutral-500 mt-12">
              Start the conversation. Try &quot;Draft a status update for a Q2 mobile launch that slipped two weeks.&quot;
            </div>
          )}

          {items.map((item) => {
            if (item.kind === "text") {
              return (
                <MessageBubble
                  key={item.key}
                  role={item.role}
                  text={item.text}
                />
              );
            }
            return (
              <ToolCallBlock
                key={item.key}
                name={item.name}
                input={item.input}
                output={item.output}
                isError={item.isError}
                status={item.status}
              />
            );
          })}

          {isStreaming && streaming && <StreamingBubble text={streaming} />}

          {liveTools.map((tc) => (
            <ToolCallBlock
              key={`live:${tc.call_id}`}
              name={tc.name}
              input={tc.input}
              output={tc.output}
              isError={tc.isError}
              status={tc.status}
            />
          ))}

          {waitingForFirstToken && (
            <div className="flex justify-start">
              <div className="bg-white border border-neutral-200 rounded-lg px-4 py-2.5 text-sm text-neutral-500">
                thinking…
              </div>
            </div>
          )}

          {lastError && (
            <Banner
              kind="warn"
              title={
                lastError.code === "MODEL_TOOL_CALL_FAILED"
                  ? "Model stumbled on a tool call"
                  : lastError.code === "MODEL_API_ERROR"
                  ? "Model service error"
                  : lastError.code === "TOOL_ERROR"
                  ? "A tool failed"
                  : lastError.code === "DB_ERROR"
                  ? "Couldn't save this turn"
                  : "Something went wrong"
              }
              onDismiss={() => clearLastError(sessionId)}
            >
              {lastError.message}
            </Banner>
          )}
        </div>
      </div>
      {awaitingReview && !isStreaming ? (
        <ApprovalBar
          review={awaitingReview}
          onApprove={handleApprove}
          onRevise={handleRevise}
          onRestart={handleRestart}
        />
      ) : (
        <ChatInput
          onSend={handleSend}
          onCancel={handleCancel}
          isStreaming={isStreaming}
        />
      )}
    </div>
  );
}
