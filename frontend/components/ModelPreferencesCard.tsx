"use client";
import { useEffect, useMemo, useState } from "react";
import { api, type ModelPreferences } from "@/lib/api";

const SLOT_HELP: Record<"light" | "heavy", string> = {
  light:
    "Used for casual chat and tool-heavy turns. Should be fast and cheap.",
  heavy:
    "Used for drafting turns (PRDs, retros, briefs) and any active skill. Quality matters more than speed.",
};

const FALLBACK_VALUE = "__FALLBACK__";

export function ModelPreferencesCard() {
  const [prefs, setPrefs] = useState<ModelPreferences | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingSlot, setSavingSlot] = useState<"light" | "heavy" | null>(null);
  const [savedSlot, setSavedSlot] = useState<"light" | "heavy" | null>(null);

  useEffect(() => {
    api
      .getModelPreferences()
      .then(setPrefs)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function update(slot: "light" | "heavy", value: string) {
    if (!prefs) return;
    const next = value === FALLBACK_VALUE ? null : value;
    setSavingSlot(slot);
    setSavedSlot(null);
    setError(null);
    try {
      const updated = await api.setModelPreferences(
        slot === "light" ? { light_model: next } : { heavy_model: next },
      );
      setPrefs(updated);
      setSavedSlot(slot);
      window.setTimeout(() => {
        setSavedSlot((cur) => (cur === slot ? null : cur));
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingSlot(null);
    }
  }

  if (error && !prefs) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700">
        Failed to load model preferences: {error}
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-medium">Model preferences</h3>
          <p className="mt-1 text-sm text-neutral-600">
            Pick which models pMomentum uses for each turn. Your choice is saved
            per user. Leave on &ldquo;Default&rdquo; to follow the env var.
          </p>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-inset ring-red-200">
          {error}
        </div>
      )}

      <ModelSlot
        slot="light"
        label="Light model"
        prefs={prefs}
        savingSlot={savingSlot}
        savedSlot={savedSlot}
        fallbackValue={FALLBACK_VALUE}
        onChange={update}
      />

      <ModelSlot
        slot="heavy"
        label="Heavy model"
        prefs={prefs}
        savingSlot={savingSlot}
        savedSlot={savedSlot}
        fallbackValue={FALLBACK_VALUE}
        onChange={update}
      />
    </div>
  );
}

interface SlotProps {
  slot: "light" | "heavy";
  label: string;
  prefs: ModelPreferences;
  savingSlot: "light" | "heavy" | null;
  savedSlot: "light" | "heavy" | null;
  fallbackValue: string;
  onChange: (slot: "light" | "heavy", value: string) => void;
}

function ModelSlot({
  slot,
  label,
  prefs,
  savingSlot,
  savedSlot,
  fallbackValue,
  onChange,
}: SlotProps) {
  const available =
    slot === "light"
      ? prefs.available_light_models
      : prefs.available_heavy_models;
  const userPick = slot === "light" ? prefs.light_model : prefs.heavy_model;
  const effective =
    slot === "light"
      ? prefs.effective_light_model
      : prefs.effective_heavy_model;

  const selectValue = userPick ?? fallbackValue;
  const isSaving = savingSlot === slot;
  const justSaved = savedSlot === slot;

  const selectedNote = useMemo(() => {
    if (!userPick) return null;
    return available.find((m) => m.id === userPick)?.notes ?? null;
  }, [userPick, available]);

  return (
    <div className="mt-5 first:mt-4">
      <div className="flex items-center justify-between">
        <label
          htmlFor={`model-slot-${slot}`}
          className="text-sm font-medium text-neutral-800"
        >
          {label}
        </label>
        <span className="text-xs text-neutral-500">
          {isSaving ? "Saving…" : justSaved ? "Saved ✓" : null}
        </span>
      </div>
      <p className="mt-0.5 text-xs text-neutral-500">{SLOT_HELP[slot]}</p>
      <select
        id={`model-slot-${slot}`}
        className="mt-2 block w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500"
        value={selectValue}
        disabled={isSaving}
        onChange={(e) => onChange(slot, e.target.value)}
      >
        <option value={fallbackValue}>
          Default (env var) — currently {effective}
        </option>
        {available.map((m) => (
          <option key={m.id} value={m.id}>
            {m.display_name}
          </option>
        ))}
      </select>
      {selectedNote && (
        <p className="mt-1 text-xs text-neutral-500">{selectedNote}</p>
      )}
      {!userPick && (
        <p className="mt-1 text-xs text-neutral-400">
          Effective model: <span className="font-mono">{effective}</span>
        </p>
      )}
    </div>
  );
}
