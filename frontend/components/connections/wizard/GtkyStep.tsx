"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { extractDetail } from "@/lib/errors";
import { Banner, SectionHeader } from "../kit";

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

export function GtkyStep({
  state,
  setState,
  uploads,
  setUploads,
}: {
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
      for (const file of Array.from(files)) {
        const res = await api.uploadDocument(file);
        setUploads([
          ...uploads,
          { name: res.title, chars: res.char_count, memories: res.memories_created },
        ]);
      }
    } catch (e) {
      setError(extractDetail(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        eyebrow="Step · Optional"
        title="Tell pmomentum about you"
        sub="A little context helps from message one. All optional — skip and add it later from chat anytime."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label style={{ color: "var(--text-muted)" }} className="block text-[12.5px] font-medium mb-1.5">
            Your name
          </label>
          <input
            className="input"
            style={{ fontFamily: "var(--font-geist-sans)" }}
            value={state.name}
            placeholder="e.g. Maria"
            onChange={(e) => setState({ ...state, name: e.target.value })}
          />
        </div>
        <div>
          <label style={{ color: "var(--text-muted)" }} className="block text-[12.5px] font-medium mb-1.5">
            Workspace name
          </label>
          <input
            className="input"
            style={{ fontFamily: "var(--font-geist-sans)" }}
            value={state.workspaceName}
            placeholder="e.g. Maria's Workspace"
            onChange={(e) => setState({ ...state, workspaceName: e.target.value })}
          />
        </div>
      </div>

      {FIELDS.map((f) => (
        <div key={f.key}>
          <label style={{ color: "var(--text-muted)" }} className="block text-[12.5px] font-medium mb-1.5">
            {f.label}
          </label>
          <textarea
            className="input"
            style={{ fontFamily: "var(--font-geist-sans)", minHeight: 72, resize: "vertical" }}
            value={state[f.key]}
            placeholder={f.placeholder}
            onChange={(e) => setState({ ...state, [f.key]: e.target.value })}
          />
        </div>
      ))}

      <div>
        <label style={{ color: "var(--text-muted)" }} className="block text-[12.5px] font-medium mb-1.5">
          Bring in existing documents
        </label>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-xl px-4 py-6 text-center transition-colors"
          style={{ background: "var(--bg-canvas)", border: "1px dashed var(--border-strong)" }}
        >
          <div style={{ color: "var(--text-muted)" }} className="text-sm">
            {uploading
              ? "Analyzing your document…"
              : "Click to upload PDF, Word, Markdown, or text"}
          </div>
          <div style={{ color: "var(--text-dim)" }} className="text-[11.5px] mt-1">
            We read it and pull out what&apos;s worth remembering — stored as
            private context in your memory, never leaves your machine.
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
              className="flex items-center justify-between rounded-lg px-3 py-2"
              style={{ background: "var(--bg-elev-2)" }}
            >
              <span style={{ color: "var(--text)" }} className="text-[13px]">
                ✓ {u.name}
              </span>
              <span style={{ color: "var(--text-dim)" }} className="text-[11.5px] mono">
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
