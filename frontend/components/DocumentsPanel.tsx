"use client";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink } from "@/components/ExternalLink";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import type { DocumentArtifact } from "@/lib/types";

const BACKEND_LABELS: Record<string, string> = {
  google_docs: "Google Docs",
  local: "Local",
};

const BACKEND_ORDER = ["google_docs", "local"];

function groupByBackend(
  docs: DocumentArtifact[],
): Record<string, DocumentArtifact[]> {
  const out: Record<string, DocumentArtifact[]> = {};
  for (const d of docs) {
    (out[d.backend] ||= []).push(d);
  }
  return out;
}

function formatUpdated(isoLike: string): string {
  try {
    const d = new Date(isoLike);
    if (isNaN(d.getTime())) return isoLike;
    return d.toLocaleString();
  } catch {
    return isoLike;
  }
}

export function DocumentsPanel() {
  const documents = useChatStore((s) => s.documents);
  const documentsLoadedAt = useChatStore((s) => s.documentsLoadedAt);
  const setDocuments = useChatStore((s) => s.setDocuments);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (documentsLoadedAt !== 0) return;
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => console.error("[docs] failed to load:", err));
  }, [documentsLoadedAt, setDocuments]);

  const grouped = useMemo(() => groupByBackend(documents), [documents]);

  if (collapsed) {
    return (
      <div className="w-10 border-l border-neutral-200 bg-neutral-50 flex flex-col items-center py-3">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="text-neutral-600 hover:text-neutral-900 text-lg"
          title="Show documents panel"
        >
          📄
        </button>
      </div>
    );
  }

  function handleRefresh() {
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => console.error("[docs] refresh failed:", err));
  }

  return (
    <aside className="w-80 shrink-0 border-l border-neutral-200 bg-neutral-50 flex flex-col min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-base">📄</span>
          <span className="font-semibold text-sm">Documents</span>
          <span className="text-xs text-neutral-500">{documents.length}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleRefresh}
            className="text-xs text-neutral-500 hover:text-neutral-900 px-1.5 py-0.5 rounded hover:bg-neutral-100"
            title="Refresh"
          >
            ↻
          </button>
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="text-xs text-neutral-500 hover:text-neutral-900 px-1.5 py-0.5 rounded hover:bg-neutral-100"
            title="Collapse"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {documents.length === 0 ? (
          <div className="p-4 text-xs text-neutral-500 leading-relaxed">
            No documents yet. When a skill produces a deliverable (a PRD,
            stakeholder update, meeting agenda), it will land here.
          </div>
        ) : (
          <div className="py-2">
            {BACKEND_ORDER.filter((b) => grouped[b]?.length).map((backend) => {
              const group = grouped[backend] ?? [];
              const label = BACKEND_LABELS[backend] ?? backend;
              return (
                <div key={backend} className="mb-3">
                  <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-neutral-500 font-semibold">
                    {label}
                    <span className="ml-1 text-neutral-400 font-normal">
                      ({group.length})
                    </span>
                  </div>
                  {group.map((d) => (
                    <div
                      key={`${d.backend}:${d.document_id}`}
                      className="px-3 py-1.5 text-xs hover:bg-white transition-colors flex items-start gap-2"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-neutral-900 truncate">
                          {d.title}
                        </div>
                        <div className="text-[11px] text-neutral-500 mt-0.5">
                          Updated {formatUpdated(d.updated_at)}
                        </div>
                      </div>
                      {d.url ? (
                        <ExternalLink
                          href={d.url}
                          className="shrink-0 inline-flex items-center gap-0.5 rounded bg-white ring-1 ring-inset ring-neutral-200 px-1.5 py-0.5 text-[10px] font-medium text-neutral-700 hover:bg-neutral-100"
                          title="Open in Google Docs"
                        >
                          Open ↗
                        </ExternalLink>
                      ) : (
                        <span
                          className="shrink-0 text-[10px] text-neutral-400 font-mono"
                          title={d.file_path ?? undefined}
                        >
                          local
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
