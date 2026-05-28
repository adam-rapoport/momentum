"use client";
import { useEffect, useState } from "react";
import { api, type ModelPreferences } from "@/lib/api";

const FALLBACK = "__FALLBACK__";

// Themed "exact model" override, hitting the existing /preferences/models
// endpoint. Provider-first setup picks a sensible default; this lets power
// users override the precise model per slot.
export function AdvancedModelPicker() {
  const [prefs, setPrefs] = useState<ModelPreferences | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingSlot, setSavingSlot] = useState<"light" | "heavy" | null>(null);

  function load() {
    api.getModelPreferences().then(setPrefs).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  async function update(slot: "light" | "heavy", value: string) {
    const next = value === FALLBACK ? null : value;
    setSavingSlot(slot);
    setError(null);
    try {
      const updated = await api.setModelPreferences(
        slot === "light" ? { light_model: next } : { heavy_model: next },
      );
      setPrefs(updated);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingSlot(null);
    }
  }

  if (!prefs) {
    return (
      <div style={{ color: "var(--text-dim)" }} className="text-sm">
        {error ? `Couldn't load models: ${error}` : "Loading models…"}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {(["light", "heavy"] as const).map((slot) => {
        const available = slot === "light" ? prefs.available_light_models : prefs.available_heavy_models;
        const pick = (slot === "light" ? prefs.light_model : prefs.heavy_model) ?? FALLBACK;
        const effective = slot === "light" ? prefs.effective_light_model : prefs.effective_heavy_model;
        return (
          <div key={slot}>
            <div className="flex items-center justify-between mb-1.5">
              <label style={{ color: "var(--text-muted)" }} className="text-[12.5px] font-medium capitalize">
                {slot} model
              </label>
              {savingSlot === slot && (
                <span style={{ color: "var(--text-dim)" }} className="text-xs">
                  Saving…
                </span>
              )}
            </div>
            <select
              className="input"
              style={{ fontFamily: "var(--font-geist-sans)" }}
              value={pick}
              disabled={savingSlot === slot || available.length === 0}
              onChange={(e) => update(slot, e.target.value)}
            >
              <option value={FALLBACK}>Default — currently {effective}</option>
              {available.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </select>
            {available.length === 0 && (
              <p style={{ color: "var(--text-dim)" }} className="text-xs mt-1">
                Connect a provider above to choose a specific {slot} model.
              </p>
            )}
          </div>
        );
      })}
      {error && (
        <p style={{ color: "var(--danger)" }} className="text-xs">
          {error}
        </p>
      )}
    </div>
  );
}
