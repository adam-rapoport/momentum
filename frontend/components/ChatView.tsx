"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/uiStore";
import { getWsClient } from "@/lib/ws";
import type {
  LiveToolCall,
  Message,
  ToolResultBlock,
} from "@/lib/types";
import { Banner, Btn } from "@/components/pm";
import { ApprovalBar } from "./ApprovalBar";
import { ChatInput } from "./ChatInput";
import { AssistantAvatar, MessageBubble, StreamingBubble } from "./MessageBubble";
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
      messageId: string;
      sendFailed: boolean;
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
          messageId: m.id,
          sendFailed: !!m.send_failed,
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
  const stopped = useChatStore((s) => s.stoppedBySession[sessionId]) ?? false;
  const setMessages = useChatStore((s) => s.setMessages);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const removeMessage = useChatStore((s) => s.removeMessage);
  const startStreaming = useChatStore((s) => s.startStreaming);
  const upsertSession = useChatStore((s) => s.upsertSession);
  const setAwaitingReview = useChatStore((s) => s.setAwaitingReview);
  const clearAwaitingReview = useChatStore((s) => s.clearAwaitingReview);
  const clearLastError = useChatStore((s) => s.clearLastError);
  const setTotalCost = useChatStore((s) => s.setTotalCost);

  const items = useMemo(() => messagesToItems(messages), [messages]);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Autoscroll only while the user is at (or near) the bottom. Scrolling up
  // to re-read mid-stream unpins; the "Jump to latest" pill brings them back.
  const pinnedRef = useRef(true);
  const [unpinned, setUnpinned] = useState(false);
  // Session fetch lifecycle. "loading" only shows when nothing is cached, so
  // switching back to an already-loaded session doesn't flash a spinner.
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const cached =
      (useChatStore.getState().messagesBySession[sessionId]?.length ?? 0) > 0;
    setLoadState(cached ? "ready" : "loading");
    api
      .getSession(sessionId)
      .then((detail) => {
        if (cancelled) return;
        setLoadState("ready");
        setMessages(sessionId, detail.messages);
        upsertSession(detail);
        if (detail.total_cost_usd != null) {
          setTotalCost(sessionId, detail.total_cost_usd);
        }
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
        // First message typed on the home screen: send it only now that the
        // initial load is done, so this fetch can't clobber the optimistic
        // user bubble.
        const queued = useUiStore.getState().queuedFirstMessage;
        if (queued && queued.sessionId === sessionId) {
          useUiStore.getState().setQueuedFirstMessage(null);
          const store = useChatStore.getState();
          store.clearLastError(sessionId);
          store.appendUserMessage(sessionId, queued.content);
          store.startStreaming(sessionId);
          getWsClient().send({
            type: "session.message",
            session_id: sessionId,
            content: queued.content,
          });
        }
      })
      .catch((err) => {
        console.error("failed to load session:", err);
        if (cancelled) return;
        // Keep showing cached messages if we have them; only the empty case
        // becomes a full error state with a retry.
        const hasCached =
          (useChatStore.getState().messagesBySession[sessionId]?.length ?? 0) > 0;
        setLoadState(hasCached ? "ready" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [
    sessionId,
    reloadKey,
    setMessages,
    upsertSession,
    setAwaitingReview,
    clearAwaitingReview,
    setTotalCost,
  ]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !pinnedRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [items.length, streaming, liveTools.length]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    pinnedRef.current = nearBottom;
    setUnpinned(!nearBottom);
  }

  function jumpToLatest() {
    const el = scrollRef.current;
    if (!el) return;
    pinnedRef.current = true;
    setUnpinned(false);
    el.scrollTop = el.scrollHeight;
  }

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

  /** Re-send a message whose original send never reached the backend: drop
   * the failed optimistic bubble, then send the same content fresh. */
  function handleRetry(messageId: string, text: string) {
    removeMessage(sessionId, messageId);
    handleSend(text);
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
    <div className="relative flex h-full min-h-0 flex-col">
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[760px] space-y-3 px-5 py-4">
          {loadState === "loading" && items.length === 0 && (
            <div className="mt-12 text-center font-mono text-[12px] text-ink-dim">
              Loading conversation…
            </div>
          )}

          {loadState === "error" && items.length === 0 && (
            <div className="mt-12 space-y-2 text-center">
              <div className="text-sm text-ink-muted">
                Couldn&apos;t load this conversation.
              </div>
              <Btn size="sm" onClick={() => setReloadKey((k) => k + 1)} className="mx-auto">
                Try again
              </Btn>
            </div>
          )}

          {loadState === "ready" && items.length === 0 && !isStreaming && (
            <div className="mt-12 text-center text-sm text-ink-dim">
              Start the conversation. Try &quot;Draft a status update for a Q2 mobile launch that slipped two weeks.&quot;
            </div>
          )}

          {items.map((item) => {
            if (item.kind === "text") {
              if (item.sendFailed) {
                return (
                  <div key={item.key}>
                    <div className="opacity-60">
                      <MessageBubble role={item.role} text={item.text} />
                    </div>
                    <div className="mt-1 flex items-center justify-end gap-2 text-xs text-danger">
                      <span>Not sent</span>
                      <button
                        type="button"
                        onClick={() => handleRetry(item.messageId, item.text)}
                        className="rounded-[6px] border border-danger/40 bg-surface px-2 py-0.5 font-medium hover:bg-danger-soft"
                      >
                        Retry
                      </button>
                    </div>
                  </div>
                );
              }
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

          {stopped && !isStreaming && (
            <div className="pl-[38px] font-mono text-[11px] text-ink-dim">■ Stopped by you</div>
          )}

          {waitingForFirstToken && (
            <div className="flex items-center gap-3">
              <AssistantAvatar pulse />
              <span className="font-mono text-[12px] text-ink-dim">thinking…</span>
            </div>
          )}

          {lastError && (
            <Banner
              kind="warn"
              title={
                lastError.code === "MODEL_TOOL_CALL_FAILED"
                  ? "Model stumbled on a tool call"
                  : lastError.code === "MODEL_AUTH_ERROR"
                  ? "Provider key problem"
                  : lastError.code === "MODEL_RATE_LIMITED"
                  ? "Rate limited by the model provider"
                  : lastError.code === "MODEL_CONTEXT_TOO_LONG"
                  ? "Conversation too long for this model"
                  : lastError.code === "MODEL_API_ERROR"
                  ? "Model service error"
                  : lastError.code === "TURN_IN_PROGRESS"
                  ? "Still responding"
                  : lastError.code === "APPROVAL_REQUIRED"
                  ? "Waiting for your decision"
                  : lastError.code === "TOOL_ERROR"
                  ? "A tool call failed (the agent kept going)"
                  : lastError.code === "DB_ERROR"
                  ? "Couldn't save this turn"
                  : lastError.code === "WS_DISCONNECTED"
                  ? "Connection dropped"
                  : lastError.code === "WS_UNAVAILABLE"
                  ? "Couldn't reach the backend"
                  : "Something went wrong"
              }
              onDismiss={() => clearLastError(sessionId)}
            >
              {lastError.code === "TOOL_ERROR" ? (
                <>
                  {/* Tool errors embed the raw call args — useful for a quick
                      glance, noise beyond a couple of lines. */}
                  <span className="break-words">
                    {lastError.message.length > 220
                      ? `${lastError.message.slice(0, 220)}…`
                      : lastError.message}
                  </span>
                  <span className="mt-1 block text-ink-dim">
                    The agent usually retries or works around a failed tool on its own — check its
                    reply for the outcome.
                  </span>
                </>
              ) : (
                lastError.message
              )}
            </Banner>
          )}
        </div>
      </div>

      {unpinned && (
        <button
          type="button"
          onClick={jumpToLatest}
          className="absolute bottom-32 left-1/2 -translate-x-1/2 rounded-full px-3 py-1.5 font-mono text-[11px] shadow-pop"
          style={{ background: "var(--text)", color: "var(--bg-app)" }}
        >
          ↓ Jump to latest
        </button>
      )}

      <div className="mx-auto w-full max-w-[760px] px-5 pb-4 pt-1">
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
    </div>
  );
}
