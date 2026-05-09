"use client";
import { useState } from "react";
import { api, type GoogleStatus } from "@/lib/api";

interface Props {
  status: GoogleStatus;
  onStatusChange: (next: GoogleStatus) => void;
}

const SERVICE_LABELS: Record<string, string> = {
  docs: "Docs",
  gmail: "Gmail",
  calendar: "Calendar",
};

const ALL_SERVICES = ["docs", "gmail", "calendar"];

export function IntegrationCard({ status, onStatusChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connected = status.status === "connected";
  const needsReconnect = status.needs_reconnect;

  async function handleConnect() {
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await api.googleConnect();
      window.location.href = authorize_url;
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleDisconnect() {
    if (
      !confirm(
        "Disconnect Google? Docs you wrote to Drive stay there. Draft emails remain in Gmail. Calendar events are not deleted.",
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.googleDisconnect();
      onStatusChange({
        ...status,
        status: "disconnected",
        connected_at: null,
        google_email: null,
        scopes: [],
        enabled_services: [],
        needs_reconnect: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const statusBadge = needsReconnect
    ? { label: "Reconnect needed", tone: "amber" as const }
    : connected
    ? { label: "Connected", tone: "emerald" as const }
    : status.status === "error"
    ? { label: "Error", tone: "amber" as const }
    : { label: "Disconnected", tone: "neutral" as const };

  const badgeTones = {
    emerald:
      "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
    amber: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
    neutral:
      "bg-neutral-100 text-neutral-600 ring-1 ring-inset ring-neutral-200",
  };
  const dotTones = {
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    neutral: "bg-neutral-400",
  };

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-base font-semibold">Google</div>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${badgeTones[statusBadge.tone]}`}
            >
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${dotTones[statusBadge.tone]}`}
              />
              {statusBadge.label}
            </span>
          </div>
          <p className="mt-1 text-sm text-neutral-600">
            One connection covers Google Docs, Drive, Gmail, and Calendar. All
            tokens are encrypted at rest. Nothing externally visible (sent
            emails, meeting invites) happens without your approval.
          </p>
          {connected && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {ALL_SERVICES.map((svc) => {
                const enabled = status.enabled_services.includes(svc);
                return (
                  <span
                    key={svc}
                    className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${
                      enabled
                        ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200"
                        : "bg-neutral-100 text-neutral-500 ring-1 ring-inset ring-neutral-200"
                    }`}
                    title={enabled ? "Authorized" : "Not yet authorized — reconnect to enable"}
                  >
                    {enabled ? "✓" : "○"} {SERVICE_LABELS[svc]}
                  </span>
                );
              })}
            </div>
          )}
          {status.google_email && (
            <div className="mt-2 text-xs text-neutral-500">
              Signed in as <span className="font-mono">{status.google_email}</span>
              {status.connected_at && (
                <>
                  {" · connected "}
                  {new Date(status.connected_at).toLocaleString()}
                </>
              )}
            </div>
          )}
          {needsReconnect && (
            <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-200">
              Reconnect to grant access to Gmail and Calendar (new in Sprint 5).
              Your existing Docs connection keeps working until you do.
            </div>
          )}
        </div>

        <div className="shrink-0 flex flex-col gap-2">
          {connected ? (
            <>
              {needsReconnect && (
                <button
                  onClick={handleConnect}
                  disabled={busy}
                  className="rounded-md bg-neutral-900 text-white text-sm font-medium px-4 py-2 hover:bg-neutral-800 disabled:opacity-60"
                >
                  {busy ? "Opening Google…" : "Reconnect"}
                </button>
              )}
              <button
                onClick={handleDisconnect}
                disabled={busy}
                className="rounded-md bg-white ring-1 ring-inset ring-neutral-300 text-neutral-700 text-sm font-medium px-4 py-2 hover:bg-neutral-50 disabled:opacity-60"
              >
                {busy ? "Disconnecting…" : "Disconnect"}
              </button>
            </>
          ) : (
            <button
              onClick={handleConnect}
              disabled={busy}
              className="rounded-md bg-neutral-900 text-white text-sm font-medium px-4 py-2 hover:bg-neutral-800 disabled:opacity-60"
            >
              {busy ? "Opening Google…" : "Connect Google"}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
          {error}
        </div>
      )}
    </div>
  );
}
