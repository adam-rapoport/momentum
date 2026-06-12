"use client";
import { useEffect, useState } from "react";
import { Banner, Btn, PixelIcon, PmLogo, PxLabel } from "@/components/pm";
import { GoogleCard } from "@/components/settings/IntegrationsPane";
import { KeyInput } from "@/components/settings/KeyInput";
import { api, type ModelEntry } from "@/lib/api";
import { providersForTier, PROVIDERS, type ProviderMeta, type Tier } from "@/lib/providers";

export interface ModelStepState {
  providerId: string | null;
  key: string;
  // Specific model pick for this slot; null = the provider's recommended
  // default for the tier.
  model: string | null;
}

export function WelcomeStep({
  onNext,
  onSkip,
  skipping,
  skipError,
}: {
  onNext: () => void;
  onSkip: () => void;
  skipping: boolean;
  skipError?: string | null;
}) {
  return (
    <div className="pt-8 text-center">
      <div className="mb-5 flex justify-center">
        <PmLogo size={44} />
      </div>
      <div className="mb-6 font-pixel text-[15px] tracking-[0.08em] text-ink">PMOMENTUM</div>
      <p className="mx-auto mb-8 max-w-md text-[14.5px] leading-relaxed text-ink-muted">
        An AI agent for product management work — PRDs, stakeholder updates, meeting prep — with
        persistent memory, running entirely on your Mac.
      </p>
      <Btn kind="primary" size="lg" onClick={onNext} className="mx-auto">
        Set up in 2 minutes
      </Btn>
      <p className="mt-4 font-mono text-[11.5px] text-ink-dim">
        you&apos;ll need one free API key · no account, no cloud
      </p>
      <button
        type="button"
        onClick={onSkip}
        disabled={skipping}
        className="mt-7 text-[12.5px] text-ink-dim underline underline-offset-2 hover:text-ink-muted"
      >
        {skipping ? "Skipping…" : "Skip — explore with no key"}
      </button>
      {skipError && (
        <div className="mx-auto mt-4 max-w-md text-left">
          <Banner kind="danger" title="Couldn't skip setup">
            {skipError}
          </Banner>
        </div>
      )}
    </div>
  );
}

export function ModelStep({
  tier,
  stepNumber,
  state,
  setState,
  error,
  configured,
  registry,
}: {
  tier: Tier;
  stepNumber: number;
  state: ModelStepState;
  setState: (s: ModelStepState) => void;
  error?: string | null;
  /** True when the selected provider already has a stored key — the step can
   * be advanced with the key field left blank. */
  configured?: boolean;
  /** Full model registry (unfiltered) — drives the per-slot model dropdown.
   * Null while loading/unavailable: the dropdown hides, defaults apply. */
  registry: ModelEntry[] | null;
}) {
  const providers = providersForTier(tier);
  const chosen: ProviderMeta | null = state.providerId ? PROVIDERS[state.providerId] : null;
  const providerModels = (registry ?? []).filter(
    (m) => chosen && m.provider === chosen.id && (m.role === tier || m.role === "either"),
  );
  const modelPick = state.model ?? chosen?.defaultModel[tier] ?? providerModels[0]?.id ?? "";

  return (
    <div className="flex flex-col gap-5">
      <div>
        <PxLabel>
          Step {stepNumber} · {tier === "light" ? "Light model" : "Heavy model"}
        </PxLabel>
        <h1 className="mt-2 text-[20px] font-bold text-ink">
          {tier === "light" ? "Pick a fast everyday model" : "Pick a smarter model for the big asks"}
        </h1>
        <p className="mt-1 text-[13px] text-ink-muted">
          {tier === "light"
            ? "Handles chat, memory recall, and tool calls. Free tiers are plenty."
            : "Used when you ask for something meaty: a PRD, a synthesis, a long rewrite."}
        </p>
      </div>

      <div className="flex flex-col gap-2.5">
        {providers.map((p) => {
          const selected = state.providerId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => setState({ providerId: p.id, key: "", model: null })}
              className={`rounded-[12px] border p-3.5 text-left transition-colors ${
                selected
                  ? "border-accent bg-accent-tint-2 shadow-[0_0_0_3px_var(--accent-tint)]"
                  : "border-line bg-surface hover:border-line-strong"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                    selected ? "border-accent" : "border-line-strong"
                  }`}
                >
                  {selected && <span className="h-2 w-2 rounded-full bg-accent" />}
                </span>
                <span className="text-[14px] font-semibold text-ink">{p.name}</span>
              </span>
              <span className="mt-1 block pl-[26px] text-[12.5px] text-ink-muted">
                {p.description}
              </span>
              <span className="mt-1 block pl-[26px] font-mono text-[11px] text-ink-dim">
                {p.pricing}
              </span>
            </button>
          );
        })}
      </div>

      {chosen?.id === "ollama" && (
        <div className="text-[12.5px] text-ink-muted">
          Local models are whatever you&apos;ve pulled with Ollama — we&apos;ll pick your first
          tool-capable one automatically. You can change it any time in Settings → Models.
        </div>
      )}

      {chosen && providerModels.length > 1 && (
        <div className="flex flex-wrap items-center gap-2.5">
          <label className="text-[12.5px] font-medium text-ink-muted">Model</label>
          <select
            value={modelPick}
            onChange={(e) => setState({ ...state, model: e.target.value })}
            className="rounded-[7px] border border-line-strong bg-surface px-2 py-1.5 text-[13px] text-ink"
          >
            {providerModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
          {state.model === null && (
            <span className="font-mono text-[10.5px] text-ink-dim">recommended</span>
          )}
        </div>
      )}

      {chosen && (
        <div className="rounded-[12px] border border-line bg-surface p-4">
          {configured && (
            <div className="mb-3.5">
              <Banner kind="success" title={`${chosen.name} is already connected`}>
                Leave the field blank to keep using your saved key, or paste a new one to replace
                it.
              </Banner>
            </div>
          )}
          <KeyInput
            provider={chosen}
            value={state.key}
            onChange={(k) => setState({ ...state, key: k })}
            autoFocus
          />
          {error && (
            <div className="mt-3.5">
              <Banner
                kind="danger"
                title={chosen.id === "ollama" ? "Couldn't set up Ollama" : "Couldn't verify that key"}
              >
                {error}
              </Banner>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolsStep({ stepNumber }: { stepNumber: number }) {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <PxLabel>Step {stepNumber} · Tools</PxLabel>
        <h1 className="mt-2 text-[20px] font-bold text-ink">Connect your tools</h1>
        <p className="mt-1 text-[13px] text-ink-muted">
          Optional — connect Google so pMomentum can draft Docs, summarize Gmail, and check your
          calendar. You can always do this later from Settings.
        </p>
      </div>
      <GoogleCard />
      <div className="flex items-center gap-3 rounded-[12px] border border-line bg-surface p-4 opacity-60 shadow-card">
        <span className="text-[12.5px] text-ink-muted">Slack, Linear, and Jira are coming soon.</span>
      </div>
    </div>
  );
}

export function DoneStep({
  lightName,
  heavyName,
  memoriesCreated,
  onFinish,
  finishing,
  error,
}: {
  lightName: string | null;
  heavyName: string | null;
  memoriesCreated: number;
  onFinish: () => void;
  finishing: boolean;
  error?: string | null;
}) {
  const [googleEmail, setGoogleEmail] = useState<string | null>(null);
  useEffect(() => {
    api
      .googleStatus()
      .then((s) => setGoogleEmail(s.status === "connected" ? (s.google_email ?? "connected") : null))
      .catch(() => setGoogleEmail(null));
  }, []);

  return (
    <div className="py-3 text-center">
      <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-full bg-accent text-accent-fg">
        <PixelIcon name="check" size={22} />
      </div>
      <h1 className="mb-2 text-[26px] font-bold tracking-tight text-ink">You&apos;re set</h1>
      <p className="mx-auto mb-6 max-w-md text-[13.5px] text-ink-muted">
        Here&apos;s what&apos;s connected. You can change any of this from Settings anytime.
      </p>

      <div className="mx-auto mb-6 flex max-w-md flex-col gap-2.5 rounded-[12px] border border-line bg-surface p-4 text-left shadow-card">
        <SummaryLine label="Light model" value={lightName} />
        <SummaryLine label="Heavy model" value={heavyName} />
        <SummaryLine label="Google" value={googleEmail ?? "not connected"} dim={!googleEmail} />
        <SummaryLine
          label="Memory & data"
          value={
            memoriesCreated > 0
              ? `on this Mac · ${memoriesCreated} ${memoriesCreated === 1 ? "memory" : "memories"} from your docs`
              : "on this Mac, encrypted"
          }
        />
      </div>

      <div className="mx-auto mb-7 max-w-md text-left">
        <div className="mb-1.5 text-center">
          <PxLabel>Try first</PxLabel>
        </div>
        <div className="flex flex-col gap-1.5 text-[12.5px] text-ink-muted">
          <span className="rounded-[8px] bg-raised px-3 py-1.5 font-mono text-[12px]">
            /write-prd for a feature you&apos;re scoping
          </span>
          <span className="rounded-[8px] bg-raised px-3 py-1.5 font-mono text-[12px]">
            &quot;Draft a status update for a launch that slipped two weeks&quot;
          </span>
        </div>
      </div>

      {error && (
        <div className="mx-auto mb-5 max-w-md text-left">
          <Banner kind="danger" title="Couldn't finish setup">
            {error} — your keys and preferences are saved; only the final &quot;done&quot; flag
            failed to record. Try again.
          </Banner>
        </div>
      )}

      <Btn kind="primary" size="lg" onClick={onFinish} disabled={finishing} className="mx-auto">
        {finishing ? "Finishing…" : error ? "Try again →" : "Start working →"}
      </Btn>
    </div>
  );
}

function SummaryLine({ label, value, dim }: { label: string; value: string | null; dim?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-[13px] text-ink-muted">{label}</span>
      <span className={`text-right text-[13px] font-medium ${value && !dim ? "text-ink" : "text-ink-dim"}`}>
        {value || "—"}
      </span>
    </div>
  );
}
