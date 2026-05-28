"use client";
import { useEffect, useState } from "react";
import {
  api,
  type ConnectionStatus,
  type KeyProvider,
  type ModelPreferences,
} from "@/lib/api";
import { extractDetail } from "@/lib/errors";
import {
  PROVIDERS,
  providersForTier,
  validateKeyFormat,
  type ProviderMeta,
  type Tier,
} from "@/lib/providers";
import { KeyInput } from "../KeyInput";
import { Banner, ProviderTile } from "../kit";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

const SLOT_COPY: Record<Tier, { title: string; sub: string }> = {
  light: {
    title: "Light model",
    sub: "Fast everyday work — summaries, tags, quick lookups. Pick the provider that powers it.",
  },
  heavy: {
    title: "Heavy model",
    sub: "The big asks — a PRD, a synthesis, a long rewrite. Pick the provider that powers it.",
  },
};

// One slot (light or heavy). Lets the user choose which provider powers it,
// connecting that provider's key inline if needed, then persists both the key
// and the slot's model preference. A provider can power both slots (e.g.
// OpenAI), in which case its key is entered once and reused.
export function SlotModelCard({
  tier,
  connections,
  onChanged,
}: {
  tier: Tier;
  connections: ConnMap;
  onChanged: () => void;
}) {
  const providers = providersForTier(tier);
  const [prefs, setPrefs] = useState<ModelPreferences | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [changingKey, setChangingKey] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadPrefs() {
    api.getModelPreferences().then(setPrefs).catch(() => setPrefs(null));
  }
  useEffect(loadPrefs, []);

  const available = prefs
    ? tier === "light"
      ? prefs.available_light_models
      : prefs.available_heavy_models
    : [];
  const effectiveId = prefs
    ? tier === "light"
      ? prefs.effective_light_model
      : prefs.effective_heavy_model
    : "";
  const effectiveEntry = available.find((m) => m.id === effectiveId) ?? null;
  // ModelEntry.provider ("groq" | "google" | "openai") matches the PROVIDERS key.
  const activeProviderId =
    effectiveEntry && providers.some((p) => p.id === effectiveEntry.provider)
      ? effectiveEntry.provider
      : null;

  // Which provider's detail panel is shown: an explicit selection, else the
  // currently-active one. Guard to providers valid for this slot.
  const shownId =
    selectedId && providers.some((p) => p.id === selectedId)
      ? selectedId
      : activeProviderId;
  const shown: ProviderMeta | null = shownId ? PROVIDERS[shownId] ?? null : null;
  const shownStatus = shown ? connections[shown.credProvider] : undefined;
  const shownConnected = shownStatus?.configured ?? false;

  async function setSlotModel(provider: ProviderMeta) {
    const model = provider.defaultModel[tier];
    if (!model) return;
    await api.setModelPreferences(
      tier === "light" ? { light_model: model } : { heavy_model: model },
    );
  }

  function onSelectTile(id: string) {
    setError(null);
    setDraft("");
    setChangingKey(false);
    setSelectedId(id);
    const provider = PROVIDERS[id];
    if (connections[provider.credProvider]?.configured) {
      // Already connected → just point this slot at it.
      setSaving(true);
      setSlotModel(provider)
        .then(() => {
          loadPrefs();
          onChanged();
        })
        .catch((e) => setError(extractDetail(e)))
        .finally(() => setSaving(false));
    }
    // Not connected → the render shows a KeyInput for `shown`.
  }

  async function saveKey() {
    if (!shown) return;
    setSaving(true);
    setError(null);
    try {
      await api.setConnection(shown.credProvider, draft.trim());
      await setSlotModel(shown);
      setDraft("");
      setChangingKey(false);
      loadPrefs();
      onChanged();
    } catch (e) {
      setError(extractDetail(e));
    } finally {
      setSaving(false);
    }
  }

  const formatOk = shown ? validateKeyFormat(shown, draft).state === "valid" : false;
  const showKeyEditor = !!shown && (!shownConnected || changingKey);
  const copy = SLOT_COPY[tier];

  return (
    <div className="card p-4">
      <div className="mb-3">
        <div style={{ color: "var(--text)" }} className="text-base font-semibold">
          {copy.title}
        </div>
        <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] mt-0.5">
          {copy.sub}
        </div>
        {effectiveEntry && (
          <div style={{ color: "var(--text-dim)" }} className="text-[12px] mt-1.5">
            Currently using{" "}
            <span style={{ color: "var(--text)" }} className="font-medium">
              {effectiveEntry.display_name}
            </span>
          </div>
        )}
      </div>

      <div
        className="grid gap-2.5"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}
      >
        {providers.map((p) => (
          <ProviderTile
            key={p.id}
            provider={p}
            selected={shownId === p.id}
            onSelect={onSelectTile}
          />
        ))}
      </div>

      {shown && (
        <div
          className="mt-3.5 pt-3.5"
          style={{ borderTop: "1px solid var(--border-faint)" }}
        >
          {!showKeyEditor ? (
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <span
                style={{ color: "var(--text-muted)" }}
                className="inline-flex items-center gap-2 text-[13px]"
              >
                <span
                  style={{ width: 6, height: 6, background: "var(--success)" }}
                  className="inline-block rounded-full"
                />
                {shownStatus?.source === "env"
                  ? `${shown.name} connected · from .env`
                  : shownStatus?.key_suffix
                  ? `${shown.name} connected · ••••${shownStatus.key_suffix}`
                  : `${shown.name} connected`}
              </span>
              <button
                className="btn small"
                onClick={() => {
                  setDraft("");
                  setError(null);
                  setChangingKey(true);
                }}
              >
                Change key
              </button>
            </div>
          ) : (
            <div>
              <KeyInput provider={shown} value={draft} onChange={setDraft} autoFocus />
              {error && (
                <div className="mt-3">
                  <Banner kind="danger" title="Couldn't verify that key">
                    {error}
                  </Banner>
                </div>
              )}
              <div className="flex justify-end gap-2 mt-3.5">
                {(shownConnected || providers.length > 1) && (
                  <button
                    className="btn ghost"
                    disabled={saving}
                    onClick={() => {
                      setChangingKey(false);
                      setSelectedId(activeProviderId);
                      setDraft("");
                      setError(null);
                    }}
                  >
                    Cancel
                  </button>
                )}
                <button
                  className="btn primary"
                  disabled={!formatOk || saving}
                  onClick={saveKey}
                >
                  {saving ? "Verifying…" : "Save"}
                </button>
              </div>
            </div>
          )}
          {error && !showKeyEditor && (
            <div className="mt-3">
              <Banner kind="danger" title="Something went wrong">
                {error}
              </Banner>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
