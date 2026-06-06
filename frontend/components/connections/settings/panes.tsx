"use client";
import { useEffect, useRef, useState } from "react";
import { api, type ConnectionStatus, type GoogleStatus, type KeyProvider } from "@/lib/api";
import { openExternal } from "@/lib/desktop";
import { WebSearchCard } from "./WebSearchCard";
import { Banner, SectionHeader, StatusPill } from "../kit";
import { SlotModelCard } from "./SlotModelCard";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

// ── Models pane ──
export function ModelsPane({ connections, onChanged }: { connections: ConnMap; onChanged: () => void }) {
  return (
    <div>
      <SectionHeader
        title="Models"
        sub="Choose which AI powers each slot. Connect a provider once and use it for either slot — free or paid."
      />
      <div className="flex flex-col gap-3.5">
        <SlotModelCard tier="light" connections={connections} onChanged={onChanged} />
        <SlotModelCard tier="heavy" connections={connections} onChanged={onChanged} />
      </div>

      <div
        className="mt-5 p-4 rounded-[10px]"
        style={{ background: "var(--bg-canvas)", border: "1px dashed var(--border-strong)" }}
      >
        <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] leading-relaxed">
          <strong style={{ color: "var(--text)" }}>About model tiers.</strong> pmomentum picks which
          model to use automatically based on the size of the request — the light model handles most
          background work; the heavy model kicks in for bigger asks like drafting a PRD.
        </div>
      </div>
    </div>
  );
}

// ── Integrations pane ──
export function IntegrationsPane({ connections, onChanged }: { connections: ConnMap; onChanged: () => void }) {
  return (
    <div>
      <SectionHeader
        title="Integrations"
        sub="Connect external accounts so pmomentum can read & write on your behalf. All optional."
      />
      <div className="flex flex-col gap-3.5">
        <GoogleCard />
        <WebSearchCard connections={connections} onChanged={onChanged} />
      </div>
    </div>
  );
}

function isFullyConnected(s: GoogleStatus | null): boolean {
  return s?.status === "connected" && !s.needs_reconnect;
}

function GoogleCard() {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [busy, setBusy] = useState(false);
  // True after we've opened the login in the browser and are waiting for the
  // user to come back. Drives the "finish in your browser" UI + polling.
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waitingRef = useRef(false);
  waitingRef.current = waiting;

  async function load() {
    try {
      const s = await api.googleStatus();
      setStatus(s);
      if (isFullyConnected(s)) setWaiting(false);
    } catch {
      setStatus(null);
    }
  }
  useEffect(() => {
    load();
    // When the user finishes the login in their browser and returns to the app,
    // the window regains focus — re-check status so the card updates on its own.
    function onFocus() {
      load();
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  // While waiting on the browser, poll status as a backstop to the focus check
  // (some setups don't fire focus reliably). Stops once connected or after ~3 min.
  useEffect(() => {
    if (!waiting) return;
    let polls = 0;
    const id = setInterval(() => {
      polls += 1;
      if (polls > 72) {
        clearInterval(id);
        return;
      }
      load();
    }, 2500);
    return () => clearInterval(id);
  }, [waiting]);

  async function connect() {
    setError(null);
    setBusy(true);
    let authorize_url: string;
    try {
      ({ authorize_url } = await api.googleConnect());
    } catch (e) {
      // Most likely the app was built without Google login credentials, or the
      // vault key is missing — surface whatever the backend told us.
      setError(e instanceof Error ? e.message : "Couldn't start the Google connection.");
      setBusy(false);
      return;
    }
    try {
      await openExternal(authorize_url);
    } catch {
      setError("Couldn't open your browser to finish signing in. Please try again.");
      setBusy(false);
      return;
    }
    setBusy(false);
    setWaiting(true);
  }
  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      await api.googleDisconnect();
      load();
    } finally {
      setBusy(false);
    }
  }

  const connected = status?.status === "connected";

  return (
    <div className="card p-4">
      <div className="grid items-center gap-3.5" style={{ gridTemplateColumns: "40px 1fr auto" }}>
        <span
          style={{ background: "#4285F4" }}
          className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-white font-semibold mono"
        >
          G
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span style={{ color: "var(--text)" }} className="text-base font-semibold">
              Google
            </span>
            <span style={{ color: "var(--text-dim)" }} className="text-[12.5px]">
              · Docs, Gmail, Calendar
            </span>
          </div>
          {connected ? (
            <StatusPill
              status={status?.needs_reconnect ? "expired" : "ok"}
              account={status?.google_email}
              error={status?.needs_reconnect ? "New permissions available — reconnect to enable them." : null}
              onFix={status?.needs_reconnect ? connect : undefined}
              fixLabel="Reconnect"
            />
          ) : (
            <div style={{ color: "var(--text-muted)" }} className="text-[13px]">
              Read &amp; draft Docs, summarize Gmail threads, check your week.
            </div>
          )}
        </div>
        <div className="flex gap-1.5">
          {connected ? (
            <button className="btn small danger-ghost" onClick={disconnect} disabled={busy}>
              Disconnect
            </button>
          ) : waiting ? (
            <button className="btn small primary" onClick={load}>
              Check now
            </button>
          ) : (
            <button className="btn small primary" onClick={connect} disabled={busy}>
              {busy ? "Opening…" : "Connect"}
            </button>
          )}
        </div>
      </div>
      {error ? (
        <div className="mt-3">
          <Banner kind="danger" title="Couldn't connect Google">
            {error}
          </Banner>
        </div>
      ) : null}
      {waiting && !connected ? (
        <div
          className="mt-3 pt-3 flex items-center justify-between gap-3 text-[12.5px]"
          style={{ borderTop: "1px solid var(--border-faint)", color: "var(--text-muted)" }}
        >
          <span>
            Continue in your browser to finish signing in, then return here — this updates
            automatically.
          </span>
          <button className="btn small" onClick={() => setWaiting(false)}>
            Cancel
          </button>
        </div>
      ) : null}
      {connected && status?.enabled_services?.length ? (
        <div className="mt-3 pt-3 flex flex-wrap gap-2" style={{ borderTop: "1px solid var(--border-faint)" }}>
          {status.enabled_services.map((s) => (
            <span key={s} className="tag success capitalize">
              ✓ {s}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ── Account pane ──
export function AccountPane({ onChanged }: { onChanged: () => void }) {
  const [wiping, setWiping] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function wipe() {
    setWiping(true);
    try {
      await Promise.all(
        (["llm:groq", "llm:google_ai", "llm:openai", "search:tavily", "search:perplexity"] as KeyProvider[]).map((p) =>
          api.deleteConnection(p).catch(() => undefined),
        ),
      );
      onChanged();
      setConfirming(false);
    } finally {
      setWiping(false);
    }
  }

  return (
    <div>
      <SectionHeader
        title="Account"
        sub="pmomentum runs locally on your machine. There's no pmomentum account — only the keys and integrations you've added."
      />
      <div className="flex flex-col gap-3.5">
        <div className="card p-4 flex items-center justify-between gap-4">
          <div>
            <div style={{ color: "var(--text)" }} className="text-sm font-semibold">
              Run setup again
            </div>
            <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] mt-1">
              Replays the first-run wizard. Your existing keys stay unless you change them.
            </div>
          </div>
          <a className="btn" href="/onboarding?restart=1">
            Restart wizard
          </a>
        </div>

        <div className="card p-4 flex items-center justify-between gap-4">
          <div>
            <div style={{ color: "var(--danger)" }} className="text-sm font-semibold">
              Wipe stored keys
            </div>
            <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] mt-1">
              Removes every API key you&apos;ve saved here. Falls back to any keys in your .env. Your
              chats stay.
            </div>
          </div>
          {confirming ? (
            <div className="flex gap-2">
              <button className="btn small" onClick={() => setConfirming(false)} disabled={wiping}>
                Cancel
              </button>
              <button
                className="btn small"
                style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                onClick={wipe}
                disabled={wiping}
              >
                {wiping ? "Wiping…" : "Confirm wipe"}
              </button>
            </div>
          ) : (
            <button
              className="btn"
              style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
              onClick={() => setConfirming(true)}
            >
              Wipe…
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── About pane ──
export function AboutPane() {
  const lines: [string, string][] = [
    ["Version", "0.4.0-dev"],
    ["Build", "web · pre-desktop"],
    ["Storage", "local Postgres · keys encrypted at rest (Fernet)"],
    ["Source", "github.com/adam-rapoport/pmomentum"],
  ];
  return (
    <div>
      <SectionHeader
        title="About"
        sub="An AI assistant for product managers. Runs locally — your data stays on your machine."
      />
      <div className="card p-4 mb-3.5 flex flex-col gap-2">
        {lines.map(([k, v]) => (
          <div
            key={k}
            className="flex justify-between text-[12.5px] pb-2"
            style={{ borderBottom: "1px solid var(--border-faint)" }}
          >
            <span style={{ color: "var(--text-muted)" }}>{k}</span>
            <span style={{ color: "var(--text)" }} className="mono">
              {v}
            </span>
          </div>
        ))}
      </div>
      <Banner kind="info" title="Privacy, in one line">
        Your API keys are encrypted at rest. pmomentum talks directly to the providers you choose —
        nothing routes through a pmomentum server.
      </Banner>
    </div>
  );
}
