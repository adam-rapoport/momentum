"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { IntegrationCard } from "@/components/IntegrationCard";
import { ModelPreferencesCard } from "@/components/ModelPreferencesCard";
import { api, type GoogleStatus } from "@/lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const search = useSearchParams();
  const googleFlag = search.get("google");

  useEffect(() => {
    api
      .googleStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  // Banner based on the ?google= query param the callback sets.
  const banner =
    googleFlag === "connected"
      ? {
          kind: "success" as const,
          message:
            "Google connected. Docs, Gmail, and Calendar are now available to the agent.",
        }
      : googleFlag === "error"
      ? {
          kind: "error" as const,
          message: `Google connection failed (${search.get("reason") || "unknown"}). Try again.`,
        }
      : null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <p className="mt-1 text-sm text-neutral-600">
        Manage third-party connections. All tokens are encrypted at rest.
      </p>

      {banner && (
        <div
          className={`mt-4 rounded-md px-3 py-2 text-sm ring-1 ring-inset ${
            banner.kind === "success"
              ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
              : "bg-red-50 text-red-800 ring-red-200"
          }`}
        >
          {banner.message}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
          Failed to load integration status: {error}
        </div>
      )}

      <div className="mt-6 space-y-6">
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 mb-2">
            Models
          </h2>
          <ModelPreferencesCard />
        </section>

        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500 mb-2">
            Integrations
          </h2>
          {status && <IntegrationCard status={status} onStatusChange={setStatus} />}
          {!status && !error && (
            <div className="rounded-lg border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
              Loading…
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
