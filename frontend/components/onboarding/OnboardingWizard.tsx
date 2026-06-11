"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Btn, IconBtn, PixelIcon, PmLogo } from "@/components/pm";
import { api, type KeyProvider } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { PROVIDERS, providersForTier, validateKeyFormat } from "@/lib/providers";
import { DoneStep, ModelStep, ToolsStep, WelcomeStep, type ModelStepState } from "./steps";
import { GtkyStep, emptyGtky, type GtkyState, type UploadedDoc } from "./GtkyStep";

type StepKey = "welcome" | "light" | "heavy" | "tools" | "gtky" | "done";

const STEPS: { key: StepKey; label: string }[] = [
  { key: "welcome", label: "Welcome" },
  { key: "light", label: "Light model" },
  { key: "heavy", label: "Heavy model" },
  { key: "tools", label: "Tools" },
  { key: "gtky", label: "About you" },
  { key: "done", label: "Done" },
];

// Every provider can fill either slot; these are just the recommended
// defaults to pre-select (Groq for fast light work, Google/Gemma for stronger
// heavy drafting). The user can switch to any other provider from the cards.
const RECOMMENDED_PROVIDER: Record<"light" | "heavy", string> = {
  light: "groq",
  heavy: "google",
};

function initialModelState(tier: "light" | "heavy"): ModelStepState {
  const list = providersForTier(tier);
  const preferred = list.find((p) => p.id === RECOMMENDED_PROVIDER[tier]) ?? list[0];
  return { providerId: preferred?.id ?? null, key: "" };
}

// First-run wizard: Welcome → Light model → Heavy model → Tools (Google) →
// About you (profile + reference docs) → Done. Full-window takeover.
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
  const [theme, setTheme] = useState<"light" | "dark">("light");
  // Which providers already have a stored/env key (e.g. a "Replay onboarding"
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

  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    if (t === "dark" || t === "light") setTheme(t);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("pmom-theme", next);
    } catch {
      // ignore
    }
  }

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
      // A provider that's already connected (replay-wizard path, or a key
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
      // inside a JSON body — errorMessage() pulls out just the detail.
      setError(errorMessage(e));
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
      setError(errorMessage(e));
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
    if (step.key === "tools") {
      setIdx(4); // optional — GoogleCard manages its own connection state
      return;
    }
    if (step.key === "gtky") {
      if (await saveProfileStep()) setIdx(5);
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
      setFinishError(errorMessage(e));
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
  const memoriesCreated = uploads.reduce((sum, u) => sum + u.memories, 0);

  return (
    <div className="flex min-h-screen flex-col items-center bg-app px-6 pb-6">
      {/* draggable top strip — the macOS traffic lights overlay here on desktop */}
      <div data-tauri-drag-region="" className="w-full pt-3.5">
        <div data-tauri-drag-region="" className="pm-traffic-spacer" />
        <div className="mx-auto flex w-full max-w-[640px] items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            <PmLogo size={15} />
            <span className="font-pixel text-[10.5px] tracking-[0.06em] text-ink-muted">
              FIRST-RUN SETUP
            </span>
          </div>
          <IconBtn
            icon={theme === "dark" ? "sun" : "moon"}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            onClick={toggleTheme}
          />
        </div>
      </div>

      <div className="flex w-full max-w-[640px] flex-1 flex-col pt-8">
        {showStepper && <StepperBar currentIdx={idx} />}

        <div className="flex-1">
          {step.key === "welcome" && (
            <WelcomeStep
              onNext={() => setIdx(1)}
              onSkip={finish}
              skipping={finishing}
              skipError={finishError}
            />
          )}
          {step.key === "light" && (
            <ModelStep
              tier="light"
              stepNumber={2}
              state={light}
              setState={setLight}
              error={error}
              configured={isConfigured(light)}
            />
          )}
          {step.key === "heavy" && (
            <ModelStep
              tier="heavy"
              stepNumber={3}
              state={heavy}
              setState={setHeavy}
              error={error}
              configured={isConfigured(heavy)}
            />
          )}
          {step.key === "tools" && <ToolsStep stepNumber={4} />}
          {step.key === "gtky" && (
            <GtkyStep
              stepNumber={5}
              state={gtky}
              setState={setGtky}
              uploads={uploads}
              setUploads={setUploads}
            />
          )}
          {step.key === "done" && (
            <DoneStep
              lightName={light.providerId ? PROVIDERS[light.providerId].name : null}
              heavyName={heavy.providerId ? PROVIDERS[heavy.providerId].name : null}
              memoriesCreated={memoriesCreated}
              onFinish={finish}
              finishing={finishing}
              error={finishError}
            />
          )}
        </div>

        {showStepper && (
          <div className="mt-8 flex items-center justify-between">
            <Btn kind="ghost" onClick={back}>
              ← Back
            </Btn>
            <div className="flex gap-2">
              {(step.key === "heavy" || step.key === "tools" || step.key === "gtky") && (
                <Btn onClick={() => setIdx(idx + 1)} disabled={saving}>
                  Skip for now
                </Btn>
              )}
              <Btn kind="primary" onClick={advance} disabled={!canAdvance() || saving}>
                {saving ? (step.key === "gtky" ? "Saving…" : "Verifying…") : "Continue →"}
              </Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StepperBar({ currentIdx }: { currentIdx: number }) {
  return (
    <div className="mb-9 flex items-center gap-2.5">
      {STEPS.map((s, i) => {
        const isCurrent = i === currentIdx;
        const isDone = i < currentIdx;
        return (
          <div key={s.key} className="flex flex-1 items-center gap-2.5 last:flex-none">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10.5px] font-semibold ${
                  isDone
                    ? "bg-accent text-accent-fg"
                    : isCurrent
                      ? "border border-accent bg-accent-tint text-accent-text"
                      : "bg-inset text-ink-dim"
                }`}
              >
                {isDone ? <PixelIcon name="check" size={9} /> : i + 1}
              </span>
              <span
                className={`whitespace-nowrap text-[12.5px] font-medium ${
                  isCurrent ? "text-ink" : isDone ? "text-ink-muted" : "text-ink-dim"
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-line" />}
          </div>
        );
      })}
    </div>
  );
}
