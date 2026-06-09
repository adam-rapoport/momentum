"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type KeyProvider } from "@/lib/api";
import { extractDetail } from "@/lib/errors";
import { PROVIDERS, providersForTier, validateKeyFormat } from "@/lib/providers";
import { Wordmark } from "../Brand";
import { ThemeToggle } from "../ThemeToggle";
import { DoneStep, ModelPickStep, WelcomeStep, type ModelStepState } from "./steps";
import { GtkyStep, emptyGtky, type GtkyState, type UploadedDoc } from "./GtkyStep";

type StepKey = "welcome" | "light" | "heavy" | "gtky" | "done";

const STEPS: { key: StepKey; label: string }[] = [
  { key: "welcome", label: "Welcome" },
  { key: "light", label: "Light model" },
  { key: "heavy", label: "Heavy model" },
  { key: "gtky", label: "About you" },
  { key: "done", label: "Done" },
];

// Every provider can now fill either slot; these are just the recommended
// defaults to pre-select (Groq for fast light work, Google/Gemma for stronger
// heavy drafting). The user can switch to any other provider from the tiles.
const RECOMMENDED_PROVIDER: Record<"light" | "heavy", string> = {
  light: "groq",
  heavy: "google",
};

function initialModelState(tier: "light" | "heavy"): ModelStepState {
  const list = providersForTier(tier);
  const preferred =
    list.find((p) => p.id === RECOMMENDED_PROVIDER[tier]) ?? list[0];
  return { providerId: preferred?.id ?? null, key: "" };
}

export function OnboardingWizard() {
  const router = useRouter();
  const [idx, setIdx] = useState(0);
  const [light, setLight] = useState<ModelStepState>(() => initialModelState("light"));
  const [heavy, setHeavy] = useState<ModelStepState>(() => initialModelState("heavy"));
  const [gtky, setGtky] = useState<GtkyState>(emptyGtky);
  const [uploads, setUploads] = useState<UploadedDoc[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [finishError, setFinishError] = useState<string | null>(null);
  // Which providers already have a stored/env key (e.g. a "Restart wizard"
  // re-run, or a key configured via Settings). Those steps are advanceable
  // without re-pasting the key — see canAdvance/saveModel.
  const [configured, setConfigured] = useState<Partial<Record<KeyProvider, boolean>>>({});

  useEffect(() => {
    let cancelled = false;
    api
      .listConnections()
      .then((r) => {
        if (cancelled) return;
        const map: Partial<Record<KeyProvider, boolean>> = {};
        for (const c of r.connections) map[c.provider] = c.configured;
        setConfigured(map);
      })
      .catch(() => undefined); // treated as "nothing configured"
    return () => {
      cancelled = true;
    };
  }, []);

  const step = STEPS[idx];

  function isConfigured(state: ModelStepState): boolean {
    if (!state.providerId) return false;
    return !!configured[PROVIDERS[state.providerId].credProvider];
  }

  function back() {
    setError(null);
    setIdx((i) => Math.max(0, i - 1));
  }

  async function saveModel(state: ModelStepState, tier: "light" | "heavy"): Promise<boolean> {
    if (!state.providerId) return false;
    const provider = PROVIDERS[state.providerId];
    const model = provider.defaultModel[tier];
    if (!model) return false;
    setSaving(true);
    setError(null);
    try {
      // A provider that's already connected (restart-wizard path, or a key
      // added via Settings) is advanceable with an empty key field — keep the
      // stored key and just record the model preference.
      if (state.key.trim()) {
        await api.setConnection(provider.credProvider, state.key.trim());
      } else if (!isConfigured(state)) {
        return false;
      }
      await api.setModelPreferences(
        tier === "light" ? { light_model: model } : { heavy_model: model },
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
    const name = gtky.name.trim();
    const workspace = gtky.workspaceName.trim();
    const hasText = gtky.role.trim() || gtky.company.trim() || gtky.goals.trim();
    if (!name && !workspace && !hasText) return true; // nothing to save
    setSaving(true);
    setError(null);
    try {
      // Name + workspace → the real user/org record (drives the Sidebar).
      if (name || workspace) {
        await api.setProfile({
          display_name: name || undefined,
          workspace_name: workspace || undefined,
        });
      }
      // Free-text context → memory records the agent can draw on.
      if (hasText) {
        await api.saveProfile({
          role: gtky.role.trim() || undefined,
          company: gtky.company.trim() || undefined,
          goals: gtky.goals.trim() || undefined,
        });
      }
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
      if (await saveModel(light, "light")) setIdx(2);
      return;
    }
    if (step.key === "heavy") {
      if (await saveModel(heavy, "heavy")) setIdx(3);
      return;
    }
    if (step.key === "gtky") {
      if (await saveProfileStep()) setIdx(4);
      return;
    }
  }

  async function finish() {
    setFinishing(true);
    setFinishError(null);
    try {
      await api.completeOnboarding();
    } catch (e) {
      // BootGate routes on completed_at: navigating to /chat with the flag
      // unset just bounces straight back here (the "onboarding ping-pong").
      // Surface the failure and let the user retry instead.
      setFinishError(extractDetail(e));
      setFinishing(false);
      return;
    }
    router.replace("/chat");
  }

  const canAdvance = () => {
    if (step.key === "light") {
      return (
        validateKeyFormat(PROVIDERS[light.providerId ?? ""], light.key).state === "valid" ||
        (isConfigured(light) && !light.key.trim())
      );
    }
    if (step.key === "heavy") {
      return (
        validateKeyFormat(PROVIDERS[heavy.providerId ?? ""], heavy.key).state === "valid" ||
        (isConfigured(heavy) && !heavy.key.trim())
      );
    }
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
            <ModelPickStep
              tier="light"
              state={light}
              setState={setLight}
              error={error}
              configured={isConfigured(light)}
            />
          )}
          {step.key === "heavy" && (
            <ModelPickStep
              tier="heavy"
              state={heavy}
              setState={setHeavy}
              error={error}
              configured={isConfigured(heavy)}
            />
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
              error={finishError}
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
