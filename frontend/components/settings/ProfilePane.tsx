"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Banner, Btn } from "@/components/pm";
import { api, type KeyProvider } from "@/lib/api";
import { useUiStore } from "@/lib/uiStore";

export function ProfilePane({ onChanged }: { onChanged: () => void }) {
  const router = useRouter();
  const closeSettings = useUiStore((s) => s.closeSettings);
  const loadProfile = useUiStore((s) => s.loadProfile);
  const [name, setName] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wiping, setWiping] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((p) => {
        setName(p.display_name ?? "");
        setWorkspace(p.workspace_name ?? "");
      })
      .catch(() => undefined);
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.setProfile({ display_name: name.trim(), workspace_name: workspace.trim() });
      loadProfile(); // refresh the sidebar footer + home greeting
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function wipe() {
    setWiping(true);
    try {
      await Promise.all(
        (
          ["llm:groq", "llm:google_ai", "llm:openai", "search:tavily", "search:perplexity"] as KeyProvider[]
        ).map((p) => api.deleteConnection(p).catch(() => undefined)),
      );
      onChanged();
      setConfirming(false);
    } finally {
      setWiping(false);
    }
  }

  return (
    <div>
      <h2 className="text-[16.5px] font-bold text-ink">Profile</h2>
      <p className="mb-4 mt-1 text-[12.5px] text-ink-muted">
        pMomentum runs locally — there&apos;s no account, just how the app addresses you.
      </p>

      <div className="rounded-[12px] border border-line bg-surface p-4 shadow-card">
        <div className="flex flex-col gap-3">
          <ProfileField label="Your name" value={name} onChange={setName} placeholder="e.g. Maria" />
          <ProfileField
            label="Workspace"
            value={workspace}
            onChange={setWorkspace}
            placeholder="e.g. Maria's Workspace"
          />
        </div>
        {error && (
          <div className="mt-3">
            <Banner kind="danger" title="Couldn't save">
              {error}
            </Banner>
          </div>
        )}
        <div className="mt-3.5 flex items-center justify-end gap-2.5">
          {saved && <span className="text-[12px] text-ok">Saved ✓</span>}
          <Btn kind="primary" size="sm" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Btn>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-4 rounded-[12px] border border-line bg-surface p-4 shadow-card">
        <div>
          <div className="text-[14px] font-semibold text-ink">Replay onboarding</div>
          <div className="mt-0.5 text-[12.5px] text-ink-muted">
            Re-run the first-run wizard. Your existing keys stay unless you change them.
          </div>
        </div>
        <Btn
          size="sm"
          onClick={() => {
            closeSettings();
            router.push("/onboarding?restart=1");
          }}
        >
          Replay
        </Btn>
      </div>

      <div className="mt-3 flex items-center justify-between gap-4 rounded-[12px] border border-line bg-surface p-4 shadow-card">
        <div>
          <div className="text-[14px] font-semibold text-danger">Wipe stored keys</div>
          <div className="mt-0.5 text-[12.5px] text-ink-muted">
            Removes every API key you&apos;ve saved here. Falls back to any keys in your .env. Your
            chats stay.
          </div>
        </div>
        {confirming ? (
          <div className="flex shrink-0 gap-2">
            <Btn size="sm" onClick={() => setConfirming(false)} disabled={wiping}>
              Cancel
            </Btn>
            <Btn size="sm" kind="danger" onClick={wipe} disabled={wiping}>
              {wiping ? "Wiping…" : "Confirm wipe"}
            </Btn>
          </div>
        ) : (
          <Btn size="sm" kind="danger" onClick={() => setConfirming(true)}>
            Wipe…
          </Btn>
        )}
      </div>
    </div>
  );
}

function ProfileField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="grid items-center gap-3" style={{ gridTemplateColumns: "110px 1fr" }}>
      <label className="text-[12.5px] font-medium text-ink-muted">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 rounded-[8px] border border-line-strong bg-surface px-3 text-[13px] text-ink outline-none placeholder:text-ink-dim focus:border-accent"
      />
    </div>
  );
}
