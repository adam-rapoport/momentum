"use client";
import { useState } from "react";
import { api, type ConnectionStatus, type KeyProvider } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { validateKeyFormat, type KeyFormatMeta } from "@/lib/providers";
import { KeyInput } from "./KeyInput";
import { Banner, ProviderGlyph, StatusPill } from "./kit";

export interface KeyCardMeta extends KeyFormatMeta {
  id: string;
  credProvider: KeyProvider;
}

// Settings card for a single API-key provider (Groq, Google, Tavily,
// Perplexity). Shows live status and an inline edit (validate-then-store).
export function ConnectionKeyCard({
  meta,
  title,
  subtitle,
  status,
  onChanged,
}: {
  meta: KeyCardMeta;
  title: string;
  subtitle?: string;
  status?: ConnectionStatus;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const source = status?.source ?? "none";
  const stored = source === "stored";
  const env = source === "env";
  const formatOk = validateKeyFormat(meta, draft).state === "valid";

  function startEdit() {
    setDraft("");
    setError(null);
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.setConnection(meta.credProvider, draft.trim());
      setEditing(false);
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
    <div className="card p-4">
      <div className="grid items-center gap-3.5" style={{ gridTemplateColumns: "40px 1fr auto" }}>
        <ProviderGlyph id={meta.id} />
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 mb-1 flex-wrap">
            <span style={{ color: "var(--text)" }} className="text-base font-semibold whitespace-nowrap">
              {title}
            </span>
            {subtitle && (
              <span style={{ color: "var(--text-dim)" }} className="text-[12.5px]">
                · {subtitle}
              </span>
            )}
          </div>
          {stored ? (
            <StatusPill
              status="ok"
              account={status?.key_suffix ? `••••${status.key_suffix}` : meta.name}
            />
          ) : env ? (
            <span style={{ color: "var(--text-muted)" }} className="inline-flex items-center gap-2 text-[13px]">
              <span style={{ width: 6, height: 6, background: "var(--success)" }} className="inline-block rounded-full" />
              Connected · from .env
            </span>
          ) : (
            <StatusPill status="disconnected" />
          )}
        </div>
        {!editing && (
          <div className="flex gap-1.5">
            {source === "none" && (
              <button className="btn small primary" onClick={startEdit}>
                Set up
              </button>
            )}
            {env && (
              <button className="btn small" onClick={startEdit}>
                Override
              </button>
            )}
            {stored && (
              <>
                <button className="btn small" onClick={startEdit}>
                  Change
                </button>
                <button className="btn small danger-ghost" onClick={remove} disabled={saving}>
                  Remove
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {editing && (
        <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border-faint)" }}>
          <KeyInput provider={meta} value={draft} onChange={setDraft} autoFocus />
          {error && (
            <div className="mt-3">
              <Banner kind="danger" title="Couldn't verify that key">
                {error}
              </Banner>
            </div>
          )}
          <div className="flex justify-end gap-2 mt-3.5">
            <button className="btn ghost" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </button>
            <button className="btn primary" onClick={save} disabled={!formatOk || saving}>
              {saving ? "Verifying…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
