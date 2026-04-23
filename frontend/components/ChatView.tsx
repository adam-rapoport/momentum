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
        // Rehydrate the pause state after a browser refresh: if the backend
        // says this session is still awaiting review, show the approval bar
        // using the persisted pending_deliverable in session_metadata.
        const pending = detail.session_metadata?.pending_deliverable;
        if (detail.status === "awaiting_review" && pending) {
          setAwaitingReview(sessionId, {
            deliverable_kind: String(pending.deliverable_kind ?? ""),
            document_id: pending.document_id
              ? String(pending.document_id)
              : null,
            summary_for_user: String(pending.summary_for_user ?? ""),
            url: pending.url ? String(pending.url) : null,
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
            <div className="rounded-md bg-amber-50 ring-1 ring-inset ring-amber-200 px-3 py-2 text-sm text-amber-900">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="font-medium">
                    {lastError.code === "MODEL_TOOL_CALL_FAILED"
                      ? "Model stumbled on a tool call"
                      : lastError.code === "MODEL_API_ERROR"
                      ? "Model service error"
                      : lastError.code === "TOOL_ERROR"
                      ? "A tool failed"
                      : lastError.code === "DB_ERROR"
                      ? "Couldn't save this turn"
                      : "Something went wrong"}
                  </div>
                  <div className="mt-0.5 text-amber-800">{lastError.message}</div>
                </div>
                <button
                  onClick={() => clearLastError(sessionId)}
                  className="shrink-0 text-amber-700 hover:text-amber-900 text-xs"
                  aria-label="Dismiss"
                >
                  ✕
                </button>
              </div>
            </div>
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
