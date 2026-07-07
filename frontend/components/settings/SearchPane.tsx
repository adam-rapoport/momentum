"use client";
import { useCallback, useEffect, useState } from "react";
import { Banner, Btn, Chip } from "@/components/pm";
import {
  api,
  type ConnectionStatus,
  type KeyProvider,
  type SearchPreferences,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { SEARCH_PROVIDERS, type SearchProviderMeta } from "@/lib/providers";
import { KeyInput } from "./KeyInput";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

// Web search — Tavily and Perplexity are interchangeable backends for the
// WebSearch tool. The toggle picks which one is active; the cards manage keys.
export function SearchPane({ connections, onChanged }: { connections: ConnMap; onChanged: () => void }) {
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
    <div>
      <h2 className="text-[16.5px] font-bold text-ink">Web search</h2>
      <p className="mb-4 mt-1 text-[12.5px] text-ink-muted">
        Which engine the WebSearch tool uses. Add the matching key below.
      </p>
      <div className="flex flex-col gap-3">
        <SearchKeyCard
          meta={SEARCH_PROVIDERS.tavily}
          title="Tavily"
          subtitle="LLM-friendly search"
          status={connections["search:tavily"]}
          active={active === "tavily"}
          onUse={() => pick("tavily")}
          onChanged={onChanged}
        />
        <SearchKeyCard
          meta={SEARCH_PROVIDERS.perplexity}
          title="Perplexity"
          subtitle="Answer-style search"
          status={connections["search:perplexity"]}
          active={active === "perplexity"}
          onUse={() => pick("perplexity")}
          onChanged={onChanged}
        />
      </div>
    </div>
  );
}

function SearchKeyCard({
  meta,
  title,
  subtitle,
  status,
  active,
  onUse,
  onChanged,
}: {
  meta: SearchProviderMeta;
  title: string;
  subtitle: string;
  status?: ConnectionStatus;
  active: boolean;
  onUse: () => void;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const source = status?.source ?? "none";
  const stored = source === "stored";
  const env = source === "env";
  const configured = stored || env;
  // Format check is advisory (KeyInput shows it); any non-empty key can be
  // saved — the backend's live validation ping is the real gate.
  const formatOk = draft.trim().length > 0;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.setConnection(meta.credProvider, draft.trim());
      setEditing(false);
      setDraft("");
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setSaving(true);
    try {
      await api.deleteConnection(meta.credProvider);
      onChanged();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className={`rounded-[12px] border bg-surface p-4 shadow-card ${
        active && configured ? "border-accent" : "border-line"
      }`}
    >
      <div className="flex items-center gap-3.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] bg-raised font-mono text-[13px] font-semibold text-ink-muted">
          {title[0]}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[14px] font-semibold text-ink">{title}</span>
            <span className="text-[12.5px] text-ink-dim">· {subtitle}</span>
            {/* "active" only counts when a key is actually present — the
                selected provider defaults to Tavily even with no key. */}
            {active && configured && <Chip tone="accent">active</Chip>}
            {active && !configured && <Chip>needs key</Chip>}
          </div>
          <div className="mt-0.5 font-mono text-[12px] text-ink-muted">
            {stored
              ? `connected · ••••${status?.key_suffix ?? ""}`
              : env
                ? "connected · from .env"
                : "not connected"}
          </div>
        </div>
        {!editing && (
          <div className="flex shrink-0 gap-1.5">
            {!active && configured && (
              <Btn size="sm" kind="primary" onClick={onUse}>
                Use
              </Btn>
            )}
            {source === "none" && (
              <Btn size="sm" kind="primary" onClick={() => { setDraft(""); setError(null); setEditing(true); }}>
                Set up
              </Btn>
            )}
            {env && (
              <Btn size="sm" onClick={() => { setDraft(""); setError(null); setEditing(true); }}>
                Override
              </Btn>
            )}
            {stored && (
              <>
                <Btn size="sm" onClick={() => { setDraft(""); setError(null); setEditing(true); }}>
                  Change
                </Btn>
                <Btn size="sm" kind="danger" onClick={remove} disabled={saving}>
                  Remove
                </Btn>
              </>
            )}
          </div>
        )}
      </div>

      {editing && (
        <div className="mt-3.5 border-t border-line-faint pt-3.5">
          <KeyInput provider={meta} value={draft} onChange={setDraft} autoFocus />
          {error && (
            <div className="mt-3">
              <Banner kind="danger" title="Couldn't verify that key">
                {error}
              </Banner>
            </div>
          )}
          <div className="mt-3.5 flex justify-end gap-2">
            <Btn kind="ghost" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </Btn>
            <Btn kind="primary" onClick={save} disabled={!formatOk || saving}>
              {saving ? "Verifying…" : "Save"}
            </Btn>
          </div>
        </div>
      )}
    </div>
  );
}
