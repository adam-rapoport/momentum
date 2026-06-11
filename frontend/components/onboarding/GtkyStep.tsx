"use client";
import { useRef, useState } from "react";
import { Banner, PixelIcon, PxLabel } from "@/components/pm";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";

export interface GtkyState {
  name: string;
  workspaceName: string;
  role: string;
  company: string;
  goals: string;
}

export const emptyGtky: GtkyState = {
  name: "",
  workspaceName: "",
  role: "",
  company: "",
  goals: "",
};

export interface UploadedDoc {
  name: string;
  chars: number;
  memories: number;
}

const FIELDS: { key: keyof GtkyState; label: string; placeholder: string }[] = [
  {
    key: "role",
    label: "Your role & how you work",
    placeholder: "e.g. Senior PM on the growth team. Prefer async, bullet-point updates over meetings.",
  },
  {
    key: "company",
    label: "Your company & product",
    placeholder: "e.g. We build a B2B analytics tool for marketing teams. Series A, ~40 people.",
  },
  {
    key: "goals",
    label: "Current goals & key stakeholders",
    placeholder: "e.g. Q3 focus is activation. Key people: Sarah (VP Eng), Priya (Data).",
  },
];

const inputClass =
  "w-full rounded-[8px] border border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none placeholder:text-ink-dim focus:border-accent";

// "About you" — optional profile + reference-document upload. The uploaded
// docs are read by the heavy model, which extracts durable facts straight
// into memory ("N memories created").
export function GtkyStep({
  stepNumber,
  state,
  setState,
  uploads,
  setUploads,
}: {
  stepNumber: number;
  state: GtkyState;
  setState: (s: GtkyState) => void;
  uploads: UploadedDoc[];
  setUploads: (u: UploadedDoc[]) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      // Accumulate locally instead of spreading the `uploads` prop each
      // iteration — that closure is stale after the first await, so a
      // multi-file selection used to record only the last file.
      let next = uploads;
      for (const file of Array.from(files)) {
        const res = await api.uploadDocument(file);
        next = [...next, { name: res.title, chars: res.char_count, memories: res.memories_created }];
        setUploads(next);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <PxLabel>Step {stepNumber} · About you · Optional</PxLabel>
        <h1 className="mt-2 text-[20px] font-bold text-ink">Tell pMomentum about you</h1>
        <p className="mt-1 text-[13px] text-ink-muted">
          A little context helps from message one. All optional — skip and add it later from chat
          anytime.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">Your name</label>
          <input
            className={inputClass}
            value={state.name}
            placeholder="e.g. Maria"
            onChange={(e) => setState({ ...state, name: e.target.value })}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">
            Workspace name
          </label>
          <input
            className={inputClass}
            value={state.workspaceName}
            placeholder="e.g. Maria's Workspace"
            onChange={(e) => setState({ ...state, workspaceName: e.target.value })}
          />
        </div>
      </div>

      {FIELDS.map((f) => (
        <div key={f.key}>
          <label className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">{f.label}</label>
          <textarea
            className={inputClass}
            style={{ minHeight: 72, resize: "vertical" }}
            value={state[f.key]}
            placeholder={f.placeholder}
            onChange={(e) => setState({ ...state, [f.key]: e.target.value })}
          />
        </div>
      ))}

      <div>
        <label className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">
          Bring in existing documents
        </label>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-[12px] border border-dashed border-line-strong bg-raised px-4 py-6 text-center transition-colors hover:border-accent"
        >
          <div className="text-sm text-ink-muted">
            {uploading ? "Analyzing your document…" : "Click to upload PDF, Word, Markdown, or text"}
          </div>
          <div className="mt-1 text-[11.5px] text-ink-dim">
            We read it and pull out what&apos;s worth remembering — stored as private context in
            your memory, never leaves your machine.
          </div>
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.md,.markdown,.txt"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {uploads.length > 0 && (
        <div className="flex flex-col gap-2">
          {uploads.map((u, i) => (
            <div
              key={`${u.name}-${i}`}
              className="flex items-center justify-between gap-3 rounded-[8px] bg-raised px-3 py-2"
            >
              <span className="flex min-w-0 items-center gap-2 text-[13px] text-ink">
                <span className="shrink-0 text-ok">
                  <PixelIcon name="check" size={11} />
                </span>
                <span className="truncate">{u.name}</span>
              </span>
              <span className="shrink-0 font-mono text-[11.5px] text-ink-dim">
                {u.chars.toLocaleString()} chars
                {u.memories > 0
                  ? ` · ${u.memories} ${u.memories === 1 ? "memory" : "memories"} created`
                  : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {error && (
        <Banner kind="danger" title="Couldn't read that file">
          {error}
        </Banner>
      )}
    </div>
  );
}
