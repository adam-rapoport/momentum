"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type ConnectionStatus, type KeyProvider, type SearchPreferences } from "@/lib/api";
import { SEARCH_PROVIDERS } from "@/lib/providers";
import { ConnectionKeyCard } from "../ConnectionKeyCard";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

// Web Search connection — Tavily and Perplexity are interchangeable backends
// for the WebSearch tool. The radio picks which one is active; the cards below
// manage each provider's key.
export function WebSearchCard({ connections, onChanged }: { connections: ConnMap; onChanged: () => void }) {
  const [prefs, setPrefs] = useState<SearchPreferences | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api.getSearchPreferences().then(setPrefs).catch(() => setPrefs(null));
  }, []);
  useEffect(load, [load, connections]);

  async function pick(provider: "tavily" | "perplexity") {
    if (saving || prefs?.provider === provider) return;
    setSaving(true);
    try {
      await api.setSearchProvider(provider);
      load();
    } finally {
      setSaving(false);
    }
  }

  const active = prefs?.provider ?? "tavily";

  return (
    <div className="flex flex-col gap-3.5">
      <div className="card p-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div style={{ color: "var(--text)" }} className="text-sm font-semibold">
              Active search provider
            </div>
            <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] mt-0.5">
              Which engine the WebSearch tool uses. Add its key below.
            </div>
          </div>
          <div
            className="inline-flex rounded-lg p-0.5"
            style={{ background: "var(--bg-inset)", border: "1px solid var(--border)" }}
          >
            {(["tavily", "perplexity"] as const).map((p) => (
              <button
                key={p}
                onClick={() => pick(p)}
                disabled={saving}
                style={{
                  background: active === p ? "var(--accent)" : "transparent",
                  color: active === p ? "var(--accent-fg)" : "var(--text-muted)",
                }}
                className="px-3 py-1 rounded-md text-[12.5px] font-medium capitalize transition-colors"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ConnectionKeyCard
        meta={SEARCH_PROVIDERS.tavily}
        title="Tavily"
        subtitle="LLM-friendly search"
        status={connections["search:tavily"]}
        onChanged={onChanged}
      />
      <ConnectionKeyCard
        meta={SEARCH_PROVIDERS.perplexity}
        title="Perplexity"
        subtitle="Answer-style search"
        status={connections["search:perplexity"]}
        onChanged={onChanged}
      />
    </div>
  );
}
