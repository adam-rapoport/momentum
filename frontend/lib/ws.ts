"use client";
import { api } from "./api";
import { getBackendToken, getWsBase } from "./desktop";
import { useChatStore } from "./store";
import type { WsInbound, WsOutbound } from "./types";

class WsClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private explicitClose = false;
  // True while we're fetching the auth token ahead of opening the socket —
  // prevents a second connect() from racing a duplicate socket into existence.
  private connecting = false;
  // Messages sent before the socket is OPEN — e.g. the very first message on a
  // brand-new session, fired before the connection finished handshaking. We
  // queue them and flush on open instead of silently dropping them (which was
  // the cause of "I asked a question and got no response" on a fresh chat).
  private pending: WsInbound[] = [];
  private pendingTimer: ReturnType<typeof setTimeout> | null = null;
  // Sessions that were mid-stream when the socket dropped. On reconnect we
  // refetch them so whatever the backend persisted (it kept running the turn
  // server-side) replaces the truncated live view.
  private resyncSessions = new Set<string>();
  // Per-session refetch sequence numbers: only the newest in-flight
  // getSession() refetch for a session may apply its result, so an
  // out-of-order response can't overwrite newer messages.
  private refetchSeq = new Map<string, number>();

  connect(): void {
    // Reset BEFORE the early returns: under React StrictMode's dev-only
    // mount→unmount→remount, the remount's connect() lands while the first
    // connect() is still fetching its token (connecting=true). It must still
    // clear the explicitClose set by the unmount's disconnect(), or the first
    // connect() aborts on resolve and the socket never opens.
    this.explicitClose = false;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    if (this.connecting) return;
    this.connecting = true;
    // Browser WebSocket clients can't set headers, so the desktop shell's
    // per-launch auth token travels as a query param (null in web dev — the
    // backend then skips the check), and the base URL follows whichever port
    // the shell chose. Both fetches are async but cached after the first call.
    Promise.all([getBackendToken(), getWsBase()]).then(([token, base]) => {
      this.connecting = false;
      if (this.explicitClose) return;
      if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
        return;
      }
      this.open(base, token);
    });
  }

  private open(base: string, token: string | null): void {
    const url = token
      ? `${base}/ws?token=${encodeURIComponent(token)}`
      : `${base}/ws`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      useChatStore.getState().setWsConnected(true);
      this.flushPending();
      // Resync any session that was streaming when the previous socket died:
      // the backend may have finished (or errored) the turn while we were
      // disconnected, and none of those events reached us.
      const toResync = [...this.resyncSessions];
      this.resyncSessions.clear();
      for (const sessionId of toResync) {
        this.refetchSession(sessionId, { clearReviewIfActive: true });
      }
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
      const store = useChatStore.getState();
      store.setWsConnected(false);
      // Finalize every in-flight stream so no session is stuck on "thinking…"
      // forever (the events that would have ended it can no longer arrive),
      // and remember them for a resync once we're back.
      for (const [sessionId, streaming] of Object.entries(store.isStreamingBySession)) {
        if (!streaming) continue;
        this.resyncSessions.add(sessionId);
        store.setLastError(sessionId, {
          code: "WS_DISCONNECTED",
          message:
            "Lost the connection to the backend mid-response. Reconnecting — the conversation will resync automatically.",
        });
        store.finalizeStream(sessionId);
      }
      if (!this.explicitClose) {
        const delay = Math.min(30000, 1000 * Math.pow(2, this.reconnectAttempts));
        this.reconnectAttempts += 1;
        this.reconnectTimer = setTimeout(() => {
          this.reconnectTimer = null;
          this.connect();
        }, delay);
      }
    };

    this.ws.onerror = (err) => {
      console.error("[ws] error:", err);
    };
  }

  disconnect(): void {
    this.explicitClose = true;
    // Kill the pending-reconnect/queue timers BEFORE closing, or a scheduled
    // reconnect fires after we're gone (zombie socket flipping the header to
    // "disconnected" / duplicating event handling).
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pendingTimer) {
      clearTimeout(this.pendingTimer);
      this.pendingTimer = null;
    }
    this.pending = [];
    if (this.ws) {
      // Detach handlers so the close of THIS socket can't mutate store state
      // owned by the next connect().
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
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
        if (m.type === "session.message") {
          // The optimistic bubble never reached the backend — mark it failed
          // so the chat offers a retry instead of showing a phantom message.
          store.markSendFailed(m.session_id);
        }
        store.finalizeStream(m.session_id);
      }
    }, 15000);
  }

  /**
   * Refetch a session's authoritative state and apply it — unless it's stale.
   * Two staleness guards:
   *   1. refetchSeq — a newer refetch for the same session started after this
   *      one; let the newest win.
   *   2. turn epoch — the user started a NEW turn while this refetch was in
   *      flight; applying now would clobber the new turn's optimistic message
   *      and kill its streaming indicator. The new turn's own stream.done
   *      refetch will deliver everything this one would have.
   */
  private refetchSession(
    sessionId: string,
    opts: {
      totalCost?: string;
      cancelled?: boolean;
      clearReviewIfActive?: boolean;
      /** Move the session to the top of the sidebar — only for refetches
       * triggered by a completed turn, never for reconnect resyncs. */
      bump?: boolean;
    } = {},
  ): void {
    const epoch = useChatStore.getState().turnEpochBySession[sessionId] ?? 0;
    const seq = (this.refetchSeq.get(sessionId) ?? 0) + 1;
    this.refetchSeq.set(sessionId, seq);
    const isStale = () =>
      this.refetchSeq.get(sessionId) !== seq ||
      (useChatStore.getState().turnEpochBySession[sessionId] ?? 0) !== epoch;
    api
      .getSession(sessionId)
      .then((detail) => {
        if (isStale()) return;
        const s = useChatStore.getState();
        s.setMessages(sessionId, detail.messages);
        // Bump before upserting so the in-place upsert then lands the
        // authoritative server record (incl. its updated_at) at the top.
        if (opts.bump) s.bumpSession(sessionId);
        s.upsertSession(detail);
        // If the backend resumed from awaiting_review (status back to
        // "active"), drop any stale approval bar on the client.
        if (opts.clearReviewIfActive && detail.status === "active") {
          s.clearAwaitingReview(sessionId);
        }
        s.finalizeStream(
          sessionId,
          opts.totalCost ?? detail.total_cost_usd,
          opts.cancelled ?? false,
        );
      })
      .catch((err) => {
        console.error("[ws] failed to refetch session:", err);
        if (isStale()) return;
        // Still finalize so the input control unlocks; pass no cost so the
        // last known value is preserved (no $0 reset on error paths).
        useChatStore
          .getState()
          .finalizeStream(sessionId, opts.totalCost, opts.cancelled ?? false);
      });
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
      this.refetchSession(sessionId, { bump: true });
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
      if (event.metadata.model) store.setLastModel(sessionId, event.metadata.model);
      this.refetchSession(sessionId, {
        totalCost: event.usage.total_cost_usd,
        cancelled: event.metadata.cancelled,
        clearReviewIfActive: true,
        bump: true,
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
    } else if (event.type === "session.renamed") {
      // The engine generated a short AI title for a new session — reflect it
      // in the sidebar + toolbar without waiting for a refetch.
      store.renameSession(event.session_id, event.title);
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
        // No cost: error paths keep the previously displayed total.
        store.finalizeStream(event.session_id);
      }
    }
  }
}

let _client: WsClient | null = null;

export function getWsClient(): WsClient {
  if (_client === null) _client = new WsClient();
  return _client;
}
