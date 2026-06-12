"use client";
import { useEffect, useState } from "react";
import { Banner, Btn, Chip, PixelIcon } from "@/components/pm";
import {
  api,
  type ConnectionStatus,
  type KeyProvider,
  type ModelPreferences,
  type OllamaModel,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import {
  PROVIDERS,
  providersForTier,
  validateKeyFormat,
  type ProviderMeta,
  type Tier,
} from "@/lib/providers";
import { KeyInput } from "./KeyInput";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

const SLOT_COPY: Record<Tier, { title: string; sub: string }> = {
  light: {
    title: "Light model",
    sub: "Fast everyday turns — chat, recall, tools",
  },
  heavy: {
    title: "Heavy model",
    sub: "Big asks — drafting, long reasoning",
  },
};

export function ModelsPane({ connections, onChanged }: { connections: ConnMap; onChanged: () => void }) {
  return (
    <div>
      <h2 className="text-[16.5px] font-bold text-ink">Models</h2>
      <p className="mb-4 mt-1 text-[12.5px] text-ink-muted">
        pMomentum routes each turn: quick turns go to the light model, drafting and skills go to
        the heavy one.
      </p>
      <div className="flex flex-col gap-3.5">
        <SlotCard tier="light" connections={connections} onChanged={onChanged} />
        <SlotCard tier="heavy" connections={connections} onChanged={onChanged} />
      </div>
    </div>
  );
}

// One slot (light or heavy). Same behavior as the pre-redesign SlotModelCard:
// pick the provider (connecting its key inline if needed), then the exact
// model. A provider can power both slots with one key.
function SlotCard({
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
  const [expanded, setExpanded] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [changingKey, setChangingKey] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Local Ollama server state — fetched live when the Ollama pill is shown.
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[] | null>(null);
  const [ollamaBase, setOllamaBase] = useState<string | null>(null);

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
  // Ollama models are dynamic (never in the registry list), so the effective
  // id is the only signal that this slot runs on the local provider.
  const isOllamaActive = effectiveId.startsWith("ollama:");
  const activeProviderId = isOllamaActive
    ? "ollama"
    : effectiveEntry && providers.some((p) => p.id === effectiveEntry.provider)
      ? effectiveEntry.provider
      : null;
  const activeProvider = activeProviderId ? PROVIDERS[activeProviderId] : null;
  const activeStatus = activeProvider ? connections[activeProvider.credProvider] : undefined;

  // Which provider's detail panel is shown while editing: an explicit
  // selection, else the currently-active one.
  const shownId =
    selectedId && providers.some((p) => p.id === selectedId) ? selectedId : activeProviderId;
  const shown: ProviderMeta | null = shownId ? (PROVIDERS[shownId] ?? null) : null;
  const shownStatus = shown ? connections[shown.credProvider] : undefined;
  const shownConnected = shownStatus?.configured ?? false;

  const showingOllama = shown?.id === "ollama";

  // Fetch the live local-model list whenever the Ollama panel is visible and
  // the connection exists (also fires right after the URL is first saved,
  // via the parent's connections refresh flipping shownConnected).
  useEffect(() => {
    if (!expanded || !showingOllama || !shownConnected) return;
    let cancelled = false;
    api
      .listOllamaModels()
      .then((r) => {
        if (cancelled) return;
        setOllamaModels(r.models);
        setOllamaBase(r.base_url);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, showingOllama, shownConnected]);

  const providerModels = shown ? available.filter((m) => m.provider === shown.id) : [];
  const slotPick = showingOllama
    ? (isOllamaActive ? effectiveId : (ollamaModels?.[0]?.id ?? ""))
    : effectiveEntry && shown && effectiveEntry.provider === shown.id
      ? effectiveId
      : (shown?.defaultModel[tier] ?? providerModels[0]?.id ?? "");

  function onSelectModel(modelId: string) {
    setSaving(true);
    setError(null);
    api
      .setModelPreferences(tier === "light" ? { light_model: modelId } : { heavy_model: modelId })
      .then(() => {
        loadPrefs();
        onChanged();
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setSaving(false));
  }

  async function setSlotModel(provider: ProviderMeta) {
    const model = provider.defaultModel[tier];
    if (!model) return;
    await api.setModelPreferences(
      tier === "light" ? { light_model: model } : { heavy_model: model },
    );
  }

  function onSelectPill(id: string) {
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
        .catch((e) => setError(errorMessage(e)))
        .finally(() => setSaving(false));
    }
    // Not connected → the editor shows a KeyInput for `shown`.
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
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const formatOk = shown ? validateKeyFormat(shown, draft).state === "valid" : false;
  const showKeyEditor = !!shown && (!shownConnected || changingKey);
  const copy = SLOT_COPY[tier];
  const maskedKey =
    activeStatus?.source === "env"
      ? "from .env"
      : activeStatus?.key_suffix
        ? `••••${activeStatus.key_suffix}`
        : null;

  return (
    <div className="rounded-[12px] border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] ${
            tier === "heavy" ? "bg-accent-tint text-accent-text" : "bg-raised text-ink-muted"
          }`}
        >
          <PixelIcon name={tier === "heavy" ? "brain" : "bolt"} size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[14.5px] font-semibold text-ink">{copy.title}</span>
            {activeProvider && (activeStatus?.configured || activeStatus?.source === "env") && (
              <Chip tone="ok">connected</Chip>
            )}
          </div>
          <div className="mt-0.5 text-[12.5px] text-ink-muted">{copy.sub}</div>
          {(effectiveEntry || isOllamaActive) && (
            <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px]">
              <span className="font-medium text-ink">
                {isOllamaActive
                  ? `Ollama (local) · ${effectiveId.slice("ollama:".length)}`
                  : `${activeProvider?.name ?? effectiveEntry?.provider} · ${effectiveEntry?.display_name}`}
              </span>
              {!isOllamaActive && maskedKey && (
                <span className="font-mono text-[11.5px] text-ink-dim">{maskedKey}</span>
              )}
            </div>
          )}
        </div>
        <Btn
          size="sm"
          onClick={() => {
            setExpanded((x) => {
              if (x) {
                setSelectedId(null);
                setChangingKey(false);
                setDraft("");
                setError(null);
              }
              return !x;
            });
          }}
        >
          {expanded ? "Done" : activeProvider ? "Change" : "Set up"}
        </Btn>
      </div>

      {expanded && (
        <div className="mt-3.5 border-t border-line-faint pt-3.5">
          <div className="flex flex-wrap gap-2">
            {providers.map((p) => {
              const sel = shownId === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => onSelectPill(p.id)}
                  className={`rounded-full border px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                    sel
                      ? "border-accent bg-accent-tint text-accent-text"
                      : "border-line-strong bg-surface text-ink-muted hover:text-ink"
                  }`}
                >
                  {p.name}
                </button>
              );
            })}
          </div>
          {shown && <div className="mt-2 text-[12px] text-ink-dim">{shown.description}</div>}

          {shown && !showKeyEditor && (
            <div className="mt-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2 text-[13px] text-ink-muted">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-ok" />
                  {showingOllama
                    ? `Ollama connected · ${ollamaBase ?? "local server"}`
                    : shownStatus?.source === "env"
                      ? `${shown.name} connected · from .env`
                      : shownStatus?.key_suffix
                        ? `${shown.name} connected · ••••${shownStatus.key_suffix}`
                        : `${shown.name} connected`}
                </span>
                <Btn
                  size="sm"
                  kind="ghost"
                  onClick={() => {
                    setDraft("");
                    setError(null);
                    setChangingKey(true);
                  }}
                >
                  {shown.secret === false ? "Change URL" : "Change key"}
                </Btn>
              </div>
              {showingOllama ? (
                ollamaModels === null ? (
                  <div className="mt-3 text-[12.5px] text-ink-dim">Looking for installed models…</div>
                ) : ollamaModels.length === 0 ? (
                  <div className="mt-3 text-[12.5px] text-ink-muted">
                    No models installed yet — run{" "}
                    <code className="font-mono text-[12px]">ollama pull llama3.1:8b</code> in
                    Terminal, then reopen this panel.
                  </div>
                ) : (
                  <>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <label className="text-[12.5px] text-ink-muted">Model</label>
                      <select
                        value={slotPick}
                        disabled={saving}
                        onChange={(e) => onSelectModel(e.target.value)}
                        className="rounded-[7px] border border-line-strong bg-surface px-2 py-1 text-[13px] text-ink"
                      >
                        {ollamaModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name}
                            {m.supports_tools ? " · tools" : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="mt-2 text-[12px] text-ink-dim">
                      pMomentum relies on tool calling — models marked &quot;tools&quot; work best.
                    </div>
                  </>
                )
              ) : (
                providerModels.length > 1 && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <label className="text-[12.5px] text-ink-muted">Model</label>
                    <select
                      value={slotPick}
                      disabled={saving}
                      onChange={(e) => onSelectModel(e.target.value)}
                      className="rounded-[7px] border border-line-strong bg-surface px-2 py-1 text-[13px] text-ink"
                    >
                      {providerModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.display_name}
                        </option>
                      ))}
                    </select>
                  </div>
                )
              )}
            </div>
          )}

          {shown && showKeyEditor && (
            <div className="mt-3">
              <KeyInput provider={shown} value={draft} onChange={setDraft} autoFocus />
              {error && (
                <div className="mt-3">
                  <Banner kind="danger" title="Couldn't verify that key">
                    {error}
                  </Banner>
                </div>
              )}
              <div className="mt-3.5 flex justify-end gap-2">
                {(shownConnected || providers.length > 1) && (
                  <Btn
                    kind="ghost"
                    disabled={saving}
                    onClick={() => {
                      setChangingKey(false);
                      setSelectedId(activeProviderId);
                      setDraft("");
                      setError(null);
                    }}
                  >
                    Cancel
                  </Btn>
                )}
                <Btn kind="primary" disabled={!formatOk || saving} onClick={saveKey}>
                  {saving ? "Verifying…" : "Save"}
                </Btn>
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
