"use client";
import { api } from "./api";
import { useChatStore } from "./store";
import type { WsInbound, WsOutbound } from "./types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE ?? "ws://localhost:8000";

class WsClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private explicitClose = false;
  // Messages sent before the socket is OPEN — e.g. the very first message on a
  // brand-new session, fired before the connection finished handshaking. We
  // queue them and flush on open instead of silently dropping them (which was
  // the cause of "I asked a question and got no response" on a fresh chat).
  private pending: WsInbound[] = [];
  private pendingTimer: ReturnType<typeof setTimeout> | null = null;

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.explicitClose = false;
    this.ws = new WebSocket(`${WS_BASE}/ws`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      useChatStore.getState().setWsConnected(true);
      this.flushPending();
    };

    this.ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as WsOutbound;
        this.handleEvent(event);
      } catch (err) {
        console.error("[ws] bad JSON:", err);
      }
    };

    this.ws.onclose = () => {
      useChatStore.getState().setWsConnected(false);
      if (!this.explicitClose) {
        const delay = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempts));
        this.reconnectAttempts += 1;
        setTimeout(() => this.connect(), delay);
      }
    };

    this.ws.onerror = (err) => {
      console.error("[ws] error:", err);
    };
  }

  disconnect(): void {
    this.explicitClose = true;
    this.ws?.close();
    this.ws = null;
  }

  send(msg: WsInbound): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
      return;
    }
    // Not open yet — queue the message and make sure we're connecting. It will
    // be flushed in onopen. A timeout guards against waiting forever if the
    // backend never comes up.
    this.pending.push(msg);
    if (
      !this.ws ||
      this.ws.readyState === WebSocket.CLOSED ||
      this.ws.readyState === WebSocket.CLOSING
    ) {
      this.connect();
    }
    this.armPendingTimeout();
  }

  /** Send everything queued while the socket was still connecting. */
  private flushPending(): void {
    if (this.pendingTimer) {
      clearTimeout(this.pendingTimer);
      this.pendingTimer = null;
    }
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const queued = this.pending;
    this.pending = [];
    for (const m of queued) this.ws.send(JSON.stringify(m));
  }

  /** If queued messages can't be sent within the window, surface an error and
   * unlock the input instead of leaving the chat spinning forever. */
  private armPendingTimeout(): void {
    if (this.pendingTimer) return; // already armed
    this.pendingTimer = setTimeout(() => {
      this.pendingTimer = null;
      if (this.pending.length === 0) return;
      const stuck = this.pending;
      this.pending = [];
      const store = useChatStore.getState();
      for (const m of stuck) {
        store.setLastError(m.session_id, {
          code: "WS_UNAVAILABLE",
          message:
            "Couldn't reach pMomentum's backend to send your message. Please make sure it's running, then try again.",
        });
        store.finalizeStream(m.session_id, "0", false);
      }
    }, 15000);
  }

  private handleEvent(event: WsOutbound): void {
    const store = useChatStore.getState();
    if (event.type === "stream.text") {
      store.appendStreamChunk(event.session_id, event.text);
    } else if (event.type === "stream.tool_start") {
      store.toolStart(event.session_id, {
        call_id: event.call_id,
        name: event.name,
        input: event.input,
      });
    } else if (event.type === "stream.tool_result") {
      store.toolResult(event.session_id, {
        call_id: event.call_id,
        output: event.output,
        is_error: event.is_error,
      });
      // Also surface the failure in the banner so the user notices without
      // having to expand the tool card. Keep it short — the expanded card
      // has the full error text. Skip for AwaitReview (that's flow control,
      // not a real failure).
      if (event.is_error && event.name !== "AwaitReview") {
        store.setLastError(event.session_id, {
          code: "TOOL_ERROR",
          message: `The ${event.name} tool failed: ${event.output.slice(0, 200)}${event.output.length > 200 ? "…" : ""}`,
        });
      }
    } else if (event.type === "stream.awaiting_review") {
      // The session paused for approval — either a skill deliverable
      // (kind='deliverable') or a staged send-side action (kind='send_email'
      // / 'create_event'). Swap the chat input for the approval bar until
      // the user replies. The backend stopped the turn without emitting
      // stream.done, so finalize the stream here too.
      const sessionId = event.session_id;
      if (event.model) store.setLastModel(sessionId, event.model);
      store.setAwaitingReview(sessionId, {
        kind: event.kind ?? "deliverable",
        deliverable_kind: event.deliverable_kind,
        document_id: event.document_id,
        summary_for_user: event.summary_for_user,
        url: event.url ?? null,
        pending_action: event.pending_action ?? null,
      });
      // Refetch so the persisted state (messages, session_metadata) is
      // canonical, then drop the live streaming state.
      api
        .getSession(sessionId)
        .then((detail) => {
          const s = useChatStore.getState();
          s.setMessages(sessionId, detail.messages);
          s.upsertSession(detail);
          s.finalizeStream(
            sessionId,
            detail.total_cost_usd ?? "0",
            false,
          );
        })
        .catch((err) => {
          console.error("[ws] failed to refetch session after pause:", err);
          useChatStore.getState().finalizeStream(sessionId, "0", false);
        });
      // A skill that pauses for review has just produced a deliverable;
      // refresh the documents panel so it shows up immediately.
      api
        .listDocuments()
        .then((docs) => useChatStore.getState().setDocuments(docs))
        .catch((err) =>
          console.error("[ws] failed to refresh documents:", err),
        );
    } else if (event.type === "stream.done") {
      // Refetch authoritative messages FIRST, THEN clear streaming state.
      // Otherwise we get a flicker: streamed text + tool cards disappear
      // and there's a ~100ms gap before the refetched messages render.
      const sessionId = event.session_id;
      const totalCost = event.usage.total_cost_usd;
      const cancelled = event.metadata.cancelled;
      if (event.metadata.model) store.setLastModel(sessionId, event.metadata.model);
      api
        .getSession(sessionId)
        .then((detail) => {
          const s = useChatStore.getState();
          s.setMessages(sessionId, detail.messages);
          // Refresh session in the sessions array so skill state (Section 15
          // metadata, pending deliverables) stays in sync with the header.
          s.upsertSession(detail);
          // If the backend resumed from awaiting_review (status back to
          // "active"), drop any stale approval bar on the client.
          if (detail.status === "active") {
            s.clearAwaitingReview(sessionId);
          }
          s.finalizeStream(sessionId, totalCost, cancelled);
        })
        .catch((err) => {
          console.error("[ws] failed to refetch session after stream.done:", err);
          // Still finalize so the input control unlocks.
          useChatStore.getState().finalizeStream(sessionId, totalCost, cancelled);
        });

      // The turn may have called SaveMemory or WriteDocument — refresh both
      // panels so new entries show up without a page reload. Independent of
      // the session refetch; failures here are non-fatal.
      api
        .listMemories()
        .then((memories) => useChatStore.getState().setMemories(memories))
        .catch((err) =>
          console.error("[ws] failed to refresh memories:", err),
        );
      api
        .listDocuments()
        .then((docs) => useChatStore.getState().setDocuments(docs))
        .catch((err) =>
          console.error("[ws] failed to refresh documents:", err),
        );
    } else if (event.type === "error") {
      // Use warn (not error) so Next.js's dev overlay doesn't pop. The
      // message surfaces inline via the lastErrorBySession store slice +
      // ChatView's banner, which is far less disruptive than a modal.
      console.warn(`[ws] server error ${event.code}: ${event.message}`);
      if (event.session_id) {
        store.setLastError(event.session_id, {
          code: event.code,
          message: event.message,
        });
        store.finalizeStream(event.session_id, "0", false);
      }
    }
  }
}

let _client: WsClient | null = null;

export function getWsClient(): WsClient {
  if (_client === null) _client = new WsClient();
  return _client;
}
