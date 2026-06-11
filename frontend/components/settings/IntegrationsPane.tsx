"use client";
import { useEffect, useRef, useState } from "react";
import { Banner, Btn, Chip } from "@/components/pm";
import { api, type GoogleStatus } from "@/lib/api";
import { openExternal } from "@/lib/desktop";
import { useUiStore } from "@/lib/uiStore";

export function IntegrationsPane() {
  const googleBanner = useUiStore((s) => s.googleBanner);
  const setGoogleBanner = useUiStore((s) => s.setGoogleBanner);
  return (
    <div>
      <h2 className="text-[16.5px] font-bold text-ink">Integrations</h2>
      <p className="mb-4 mt-1 text-[12.5px] text-ink-muted">
        Connect external accounts so pMomentum can read &amp; write on your behalf. All optional.
      </p>
      {googleBanner && (
        <div className="mb-4">
          <Banner kind={googleBanner.kind} onDismiss={() => setGoogleBanner(null)}>
            {googleBanner.message}
          </Banner>
        </div>
      )}
      <div className="flex flex-col gap-3">
        <GoogleCard />
        <SoonCard name="Slack" blurb="Post updates, summarize channels" />
        <SoonCard name="Linear" blurb="Create and triage issues" />
        <SoonCard name="Jira" blurb="Sync tickets and sprints" />
      </div>
    </div>
  );
}

function SoonCard({ name, blurb }: { name: string; blurb: string }) {
  return (
    <div className="flex items-center gap-3.5 rounded-[12px] border border-line bg-surface p-4 opacity-60 shadow-card">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] bg-raised font-mono text-[13px] font-semibold text-ink-muted">
        {name[0]}
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-[14px] font-semibold text-ink">{name}</span>
        <div className="mt-0.5 text-[12.5px] text-ink-muted">{blurb}</div>
      </div>
      <Chip mono>soon</Chip>
    </div>
  );
}

function isFullyConnected(s: GoogleStatus | null): boolean {
  return s?.status === "connected" && !s.needs_reconnect;
}

// Ported behavior from the pre-redesign GoogleCard: connect via the OS
// browser, focus + interval polling while waiting, reconnect when new scopes
// are available, disconnect.
export function GoogleCard() {
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
    <div className="rounded-[12px] border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center gap-3.5">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] font-mono text-[13px] font-semibold text-white"
          style={{ background: "#4285F4" }}
        >
          G
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[14px] font-semibold text-ink">Google</span>
            <span className="text-[12.5px] text-ink-dim">· Docs, Gmail, Calendar</span>
            {connected &&
              (status?.needs_reconnect ? <Chip tone="warn">reconnect</Chip> : <Chip tone="ok">connected</Chip>)}
          </div>
          {connected ? (
            <div className="mt-0.5 font-mono text-[12px] text-ink-muted">
              {status?.google_email}
              {status?.needs_reconnect && (
                <span className="ml-2 font-sans text-ink-dim">
                  New permissions available — reconnect to enable them.
                </span>
              )}
            </div>
          ) : (
            <div className="mt-0.5 text-[12.5px] text-ink-muted">
              Read &amp; draft Docs, summarize Gmail threads, check your week.
            </div>
          )}
        </div>
        <div className="flex shrink-0 gap-1.5">
          {connected ? (
            <>
              {status?.needs_reconnect && (
                <Btn size="sm" kind="primary" onClick={connect} disabled={busy}>
                  Reconnect
                </Btn>
              )}
              <Btn size="sm" kind="danger" onClick={disconnect} disabled={busy}>
                Disconnect
              </Btn>
            </>
          ) : waiting ? (
            <Btn size="sm" kind="primary" onClick={load}>
              Check now
            </Btn>
          ) : (
            <Btn size="sm" kind="primary" onClick={connect} disabled={busy}>
              {busy ? "Opening…" : "Connect"}
            </Btn>
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
        <div className="mt-3 flex items-center justify-between gap-3 border-t border-line-faint pt-3 text-[12.5px] text-ink-muted">
          <span>
            Continue in your browser to finish signing in, then return here — this updates
            automatically.
          </span>
          <Btn size="sm" onClick={() => setWaiting(false)}>
            Cancel
          </Btn>
        </div>
      ) : null}
      {connected && status?.enabled_services?.length ? (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-line-faint pt-3">
          {status.enabled_services.map((s) => (
            <Chip key={s} tone="ok" className="capitalize">
              ✓ {s}
            </Chip>
          ))}
        </div>
      ) : null}
    </div>
  );
}
