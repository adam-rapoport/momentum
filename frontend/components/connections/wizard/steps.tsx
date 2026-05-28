"use client";
import { providersForTier, PROVIDERS, type ProviderMeta, type Tier } from "@/lib/providers";
import { Mark } from "../Brand";
import { KeyInput } from "../KeyInput";
import { Banner, ProviderTile, SectionHeader } from "../kit";

export interface ModelStepState {
  providerId: string | null;
  key: string;
}

export function WelcomeStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="text-center pt-5">
      <div className="flex justify-center mb-7">
        <Mark size={64} />
      </div>
      <h1 style={{ color: "var(--text)" }} className="text-3xl font-semibold tracking-tight mb-3">
        Welcome to pmomentum.
      </h1>
      <p style={{ color: "var(--text-muted)" }} className="text-base max-w-md mx-auto mb-8 leading-relaxed">
        A few minutes of setup and you&apos;ll be chatting. We&apos;ll connect the AI models that
        power pmomentum first — then anything else can wait.
      </p>
      <button className="btn large primary" onClick={onNext}>
        Get started →
      </button>
      <p style={{ color: "var(--text-dim)" }} className="text-[12.5px] mt-6">
        Everything stays on your machine. Your keys never leave this app.
      </p>
    </div>
  );
}

export function ModelPickStep({
  tier,
  state,
  setState,
  error,
}: {
  tier: Tier;
  state: ModelStepState;
  setState: (s: ModelStepState) => void;
  error?: string | null;
}) {
  const providers = providersForTier(tier);
  const chosen: ProviderMeta | null = state.providerId ? PROVIDERS[state.providerId] : null;

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        eyebrow={tier === "light" ? "Step · Light model" : "Step · Heavy model"}
        title={tier === "light" ? "Pick a fast everyday model" : "Pick a smarter model for the big asks"}
        sub={
          tier === "light"
            ? "Used for routine work pmomentum does in the background: summaries, tags, quick lookups."
            : "Used when you ask for something meaty: a PRD, a synthesis, a long doc rewrite."
        }
      />

      <div className="grid gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
        {providers.map((p) => (
          <ProviderTile
            key={p.id}
            provider={p}
            selected={state.providerId === p.id}
            onSelect={(id) => setState({ providerId: id, key: "" })}
          />
        ))}
      </div>

      {chosen && (
        <div
          style={{ background: "var(--bg-canvas)", borderColor: "var(--border)" }}
          className="mt-2 p-4 border rounded-xl"
        >
          <KeyInput
            provider={chosen}
            value={state.key}
            onChange={(k) => setState({ ...state, key: k })}
            autoFocus
          />
          {error && (
            <div className="mt-3.5">
              <Banner kind="danger" title="Couldn't verify that key">
                {error}
              </Banner>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DoneStep({
  lightName,
  heavyName,
  onFinish,
  finishing,
}: {
  lightName: string | null;
  heavyName: string | null;
  onFinish: () => void;
  finishing: boolean;
}) {
  return (
    <div className="text-center py-3">
      <div
        style={{ background: "var(--success-soft)", color: "var(--success)" }}
        className="inline-flex items-center justify-center w-14 h-14 rounded-2xl text-3xl mb-4"
      >
        ✓
      </div>
      <h1 style={{ color: "var(--text)" }} className="text-3xl font-semibold tracking-tight mb-3">
        You&apos;re set up.
      </h1>
      <p style={{ color: "var(--text-muted)" }} className="text-[15px] max-w-md mx-auto mb-6">
        Here&apos;s what&apos;s connected. You can change any of this from Settings anytime.
      </p>

      <div
        style={{ background: "var(--bg-canvas)", borderColor: "var(--border)" }}
        className="text-left max-w-md mx-auto mb-7 border rounded-xl p-4 flex flex-col gap-3"
      >
        <SummaryLine label="Light model" value={lightName} />
        <SummaryLine label="Heavy model" value={heavyName} />
      </div>

      <button className="btn large primary" onClick={onFinish} disabled={finishing}>
        {finishing ? "Finishing…" : "Start chatting →"}
      </button>
    </div>
  );
}

function SummaryLine({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span style={{ color: "var(--text-muted)" }} className="text-[13px]">
        {label}
      </span>
      <span
        style={{ color: value ? "var(--text)" : "var(--text-dim)" }}
        className="text-[13.5px] font-medium"
      >
        {value || "—"}
      </span>
    </div>
  );
}
