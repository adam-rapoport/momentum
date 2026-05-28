"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { extractDetail } from "@/lib/errors";
import { PROVIDERS, providersForTier, validateKeyFormat } from "@/lib/providers";
import { Wordmark } from "../Brand";
import { ThemeToggle } from "../ThemeToggle";
import { DoneStep, ModelPickStep, WelcomeStep, type ModelStepState } from "./steps";
import { GtkyStep, emptyGtky, type GtkyState } from "./GtkyStep";

type StepKey = "welcome" | "light" | "heavy" | "gtky" | "done";

const STEPS: { key: StepKey; label: string }[] = [
  { key: "welcome", label: "Welcome" },
  { key: "light", label: "Light model" },
  { key: "heavy", label: "Heavy model" },
  { key: "gtky", label: "About you" },
  { key: "done", label: "Done" },
];

function initialModelState(tier: "light" | "heavy"): ModelStepState {
  const only = providersForTier(tier);
  return { providerId: only.length === 1 ? only[0].id : null, key: "" };
}

export function OnboardingWizard() {
  const router = useRouter();
  const [idx, setIdx] = useState(0);
  const [light, setLight] = useState<ModelStepState>(() => initialModelState("light"));
  const [heavy, setHeavy] = useState<ModelStepState>(() => initialModelState("heavy"));
  const [gtky, setGtky] = useState<GtkyState>(emptyGtky);
  const [uploads, setUploads] = useState<{ name: string; chars: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const step = STEPS[idx];

  function back() {
    setError(null);
    setIdx((i) => Math.max(0, i - 1));
  }

  async function saveModel(state: ModelStepState): Promise<boolean> {
    if (!state.providerId) return false;
    const provider = PROVIDERS[state.providerId];
    setSaving(true);
    setError(null);
    try {
      await api.setConnection(provider.credProvider, state.key.trim());
      await api.setModelPreferences(
        provider.tier === "light"
          ? { light_model: provider.defaultModel }
          : { heavy_model: provider.defaultModel },
      );
      return true;
    } catch (e) {
      // The PUT endpoint returns 400 with the provider's rejection detail
      // inside a JSON body, wrapped by our fetch helper as
      // "400 Bad Request: {\"detail\":\"...\"}". Pull out just the detail.
      setError(extractDetail(e));
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function saveProfileStep(): Promise<boolean> {
    const hasText = gtky.role.trim() || gtky.company.trim() || gtky.goals.trim();
    if (!hasText) return true; // nothing to save; uploads already persisted
    setSaving(true);
    setError(null);
    try {
      await api.saveProfile({
        role: gtky.role.trim() || undefined,
        company: gtky.company.trim() || undefined,
        goals: gtky.goals.trim() || undefined,
      });
      return true;
    } catch (e) {
      setError(extractDetail(e));
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function advance() {
    if (step.key === "welcome") {
      setIdx(1);
      return;
    }
    if (step.key === "light") {
      if (await saveModel(light)) setIdx(2);
      return;
    }
    if (step.key === "heavy") {
      if (await saveModel(heavy)) setIdx(3);
      return;
    }
    if (step.key === "gtky") {
      if (await saveProfileStep()) setIdx(4);
      return;
    }
  }

  async function finish() {
    setFinishing(true);
    try {
      await api.completeOnboarding();
    } catch {
      /* non-fatal; gating is key-based */
    }
    router.replace("/chat");
  }

  const canAdvance = () => {
    if (step.key === "light") return validateKeyFormat(PROVIDERS[light.providerId ?? ""], light.key).state === "valid";
    if (step.key === "heavy") return validateKeyFormat(PROVIDERS[heavy.providerId ?? ""], heavy.key).state === "valid";
    return true;
  };

  const showStepper = idx > 0 && idx < STEPS.length - 1;

  return (
    <div className="min-h-full flex flex-col items-center px-6 pt-10 pb-6" style={{ background: "var(--bg-page)" }}>
      <div className="w-full max-w-2xl flex flex-col flex-1">
        <div className="mb-8 flex justify-between items-center">
          <Wordmark size={26} />
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <span style={{ color: "var(--text-dim)" }} className="text-xs whitespace-nowrap">
              First-run setup
            </span>
          </div>
        </div>

        {showStepper && <StepperBar currentIdx={idx} />}

        <div className="flex-1">
          {step.key === "welcome" && <WelcomeStep onNext={() => setIdx(1)} />}
          {step.key === "light" && (
            <ModelPickStep tier="light" state={light} setState={setLight} error={error} />
          )}
          {step.key === "heavy" && (
            <ModelPickStep tier="heavy" state={heavy} setState={setHeavy} error={error} />
          )}
          {step.key === "gtky" && (
            <GtkyStep state={gtky} setState={setGtky} uploads={uploads} setUploads={setUploads} />
          )}
          {step.key === "done" && (
            <DoneStep
              lightName={light.providerId ? PROVIDERS[light.providerId].name : null}
              heavyName={heavy.providerId ? PROVIDERS[heavy.providerId].name : null}
              onFinish={finish}
              finishing={finishing}
            />
          )}
        </div>

        {showStepper && (
          <div className="mt-8 flex justify-between items-center">
            <button className="btn ghost" onClick={back}>
              ← Back
            </button>
            <div className="flex gap-2">
              {step.key === "gtky" && (
                <button className="btn" onClick={() => setIdx(4)} disabled={saving}>
                  Skip for now
                </button>
              )}
              <button className="btn primary" onClick={advance} disabled={!canAdvance() || saving}>
                {saving ? (step.key === "gtky" ? "Saving…" : "Verifying…") : "Continue →"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StepperBar({ currentIdx }: { currentIdx: number }) {
  return (
    <div className="flex items-center gap-2.5 mb-9">
      {STEPS.map((s, i) => {
        const isCurrent = i === currentIdx;
        const isDone = i < currentIdx;
        return (
          <div key={s.key} className="flex items-center gap-2.5 flex-1 last:flex-none">
            <div className="flex items-center gap-2">
              <span
                style={{
                  background: isCurrent ? "var(--accent)" : isDone ? "var(--success-soft)" : "var(--bg-elev-2)",
                  color: isCurrent ? "var(--accent-fg)" : isDone ? "var(--success)" : "var(--text-muted)",
                  border: isCurrent || isDone ? "none" : "1px solid var(--border)",
                }}
                className="w-[22px] h-[22px] rounded-full inline-flex items-center justify-center text-[11px] font-semibold mono"
              >
                {isDone ? "✓" : i + 1}
              </span>
              <span
                style={{ color: isCurrent ? "var(--text)" : isDone ? "var(--text-muted)" : "var(--text-dim)" }}
                className="text-[12.5px] font-medium whitespace-nowrap"
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ background: "var(--border)" }} className="flex-1 h-px" />
            )}
          </div>
        );
      })}
    </div>
  );
}
