"use client";
import { useState } from "react";
import { api, type GoogleStatus } from "@/lib/api";

interface Props {
  status: GoogleStatus;
  onStatusChange: (next: GoogleStatus) => void;
}

export function IntegrationCard({ status, onStatusChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connected = status.status === "connected";

  async function handleConnect() {
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await api.googleConnect();
      // Full-page redirect to Google's consent screen. After the user
      // approves, Google redirects to /api/v1/integrations/google/callback
      // which then redirects back to /settings?google=connected.
      window.location.href = authorize_url;
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleDisconnect() {
    if (!confirm("Disconnect Google Docs? Documents you wrote to Google stay in your Drive.")) {
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
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-base font-semibold">Google Docs</div>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                connected
                  ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200"
                  : status.status === "error"
                  ? "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200"
                  : "bg-neutral-100 text-neutral-600 ring-1 ring-inset ring-neutral-200"
              }`}
            >
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  connected
                    ? "bg-emerald-500"
                    : status.status === "error"
                    ? "bg-amber-500"
                    : "bg-neutral-400"
                }`}
              />
              {connected ? "Connected" : status.status === "error" ? "Error" : "Disconnected"}
            </span>
          </div>
          <p className="mt-1 text-sm text-neutral-600">
            When connected, WriteDocument creates real Google Docs in your Drive.
            When disconnected, documents are saved as local markdown files.
          </p>
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
        </div>

        <div className="shrink-0">
          {connected ? (
            <button
              onClick={handleDisconnect}
              disabled={busy}
              className="rounded-md bg-white ring-1 ring-inset ring-neutral-300 text-neutral-700 text-sm font-medium px-4 py-2 hover:bg-neutral-50 disabled:opacity-60"
            >
              {busy ? "Disconnecting…" : "Disconnect"}
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={busy}
              className="rounded-md bg-neutral-900 text-white text-sm font-medium px-4 py-2 hover:bg-neutral-800 disabled:opacity-60"
            >
              {busy ? "Opening Google…" : "Connect Google Docs"}
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
