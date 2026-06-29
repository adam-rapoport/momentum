"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink } from "@/components/ExternalLink";
import { Chip, IconBtn, PixelIcon, PxLabel, Segmented, type PixelIconName } from "@/components/pm";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { isTauri, openLocalPath, revealInFolder } from "@/lib/desktop";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/uiStore";
import type {
  DocumentArtifact,
  MemoryRecordDetail,
  MemoryRecordSummary,
  MemoryType,
} from "@/lib/types";

// Links inside memory bodies must open via the OS browser in the desktop
// webview (plain anchors are dead there).
const MD_COMPONENTS: Components = { a: ExternalLink };

const TYPE_LABELS: Record<MemoryType, string> = {
  stakeholder: "Stakeholders",
  decision: "Decisions",
  product: "Product",
  team: "Team",
  lessons: "Lessons",
  reference: "References",
};

const TYPE_ORDER: MemoryType[] = ["stakeholder", "decision", "product", "team", "lessons", "reference"];

const TYPE_ICONS: Record<MemoryType, PixelIconName> = {
  stakeholder: "user",
  decision: "check",
  product: "box",
  team: "users",
  lessons: "sparkle",
  reference: "link",
};

function groupByType(records: MemoryRecordSummary[]): Record<string, MemoryRecordSummary[]> {
  const out: Record<string, MemoryRecordSummary[]> = {};
  for (const r of records) (out[r.type] ||= []).push(r);
  return out;
}

// Render a memory's tags. A `source:<doc>` tag (stamped by the doc-extraction
// pipeline) is surfaced as an explicit "From: <document>" line instead of a raw
// chip, and the now-redundant generic "from-document" chip is hidden.
function MemoryTags({ tags }: { tags: string[] }) {
  const sourceTag = tags.find((t) => t.startsWith("source:"));
  const sourceDoc = sourceTag?.slice("source:".length).trim();
  const chips = tags.filter((t) => !t.startsWith("source:") && t !== "from-document");
  return (
    <div className="mb-2 flex flex-col gap-1.5">
      {sourceDoc && (
        <div className="flex items-center gap-1.5 text-[11.5px] text-ink-muted">
          <PixelIcon name="doc" size={10} />
          <span>
            From: <span className="font-medium text-ink">{sourceDoc}</span>
          </span>
        </div>
      )}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-[5px]">
          {chips.map((tag) => (
            <Chip key={tag} mono>
              {tag}
            </Chip>
          ))}
        </div>
      )}
    </div>
  );
}

function MemoryTab() {
  const memories = useChatStore((s) => s.memories);
  const memoriesLoadedAt = useChatStore((s) => s.memoriesLoadedAt);
  const setMemories = useChatStore((s) => s.setMemories);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MemoryRecordDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const memoryCollapsed = useUiStore((s) => s.memoryCollapsed);
  const toggleMemoryCategory = useUiStore((s) => s.toggleMemoryCategory);

  // Search over memory names + contents. Mirrors the sidebar chat search:
  // instant client-side name filter while typing, debounced server query for
  // content matches.
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryRecordSummary[] | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadNote, setUploadNote] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function handleFilesPicked(files: FileList | File[] | null | undefined) {
    const list = files ? Array.from(files) : [];
    if (list.length === 0 || uploading) return;
    setUploading(true);
    setUploadNote(null);
    try {
      let totalMemories = 0;
      let lastTitle = "";
      for (const file of list) {
        const r = await api.uploadMemoryDocument(file);
        totalMemories += r.memories_created;
        lastTitle = r.title;
      }
      const from = list.length === 1 ? `“${lastTitle}”` : `${list.length} documents`;
      setUploadNote({
        kind: "ok",
        text: `${totalMemories} ${totalMemories === 1 ? "memory" : "memories"} created from ${from}`,
      });
      const fresh = await api.listMemories();
      setMemories(fresh);
    } catch (err) {
      setUploadNote({ kind: "err", text: errorMessage(err) });
    } finally {
      setUploading(false);
      // Reset so picking the same file again re-fires onChange.
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Success notes fade out on their own; errors stay until the next attempt.
  useEffect(() => {
    if (uploadNote?.kind !== "ok") return;
    const timer = setTimeout(() => setUploadNote(null), 6000);
    return () => clearTimeout(timer);
  }, [uploadNote]);

  // Initial load. BootGate already waits for the backend before this mounts,
  // but retry a few times anyway so a single transient failure can't leave the
  // panel permanently blank (the memoriesLoadedAt guard means it won't re-run).
  useEffect(() => {
    if (memoriesLoadedAt !== 0) return;
    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      api
        .listMemories()
        .then((m) => {
          if (!cancelled) setMemories(m);
        })
        .catch((err) => {
          console.error("[memory] failed to load:", err);
          if (!cancelled && attempts < 5) {
            attempts += 1;
            timer = setTimeout(load, 1000);
          }
        });
    };
    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [memoriesLoadedAt, setMemories]);

  // Fetch detail when selection changes
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    api
      .getMemory(selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("[memory] failed to load detail:", err);
        setDetailError(String(err));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // Debounced server-side search over names + contents (search_text). Empty
  // query clears it; the full grouped list shows instead.
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setSearchResults(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .listMemories(undefined, q)
        .then((r) => {
          if (!cancelled) setSearchResults(r);
        })
        .catch((err) => console.error("memory search failed:", err));
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const searching = query.trim().length > 0;
  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    // While searching: use the server results (name + content matches) once
    // they arrive; until then fall back to an instant client-side filter over
    // the already-loaded names/summaries.
    const visible = q
      ? (searchResults ??
          memories.filter(
            (m) =>
              m.title.toLowerCase().includes(q) ||
              (m.summary ?? "").toLowerCase().includes(q),
          ))
      : memories;
    return groupByType(visible);
  }, [memories, query, searchResults]);
  const hasMatches = TYPE_ORDER.some((t) => grouped[t]?.length);

  return (
    <div
      className={`relative flex min-h-0 flex-1 flex-col ${dragOver ? "ring-2 ring-inset ring-accent" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!uploading) setDragOver(true);
      }}
      onDragLeave={(e) => {
        // Only clear when leaving the panel itself, not crossing a child.
        if (e.currentTarget === e.target) setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        void handleFilesPicked(e.dataTransfer.files);
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.md,.markdown,.txt"
        multiple
        className="hidden"
        onChange={(e) => handleFilesPicked(e.target.files)}
      />
      {dragOver && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-panel/80 text-[12.5px] font-medium text-accent-text">
          Drop documents to add them to memory
        </div>
      )}
      <div className="flex items-center justify-between gap-2 border-b border-line-faint px-4 py-2">
        <button
          type="button"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-[7px] border border-line bg-surface px-2.5 py-1 text-[11.5px] font-medium text-ink-muted shadow-card transition-colors duration-100 hover:border-accent hover:text-ink disabled:cursor-default disabled:opacity-60"
        >
          <PixelIcon name="plus" size={10} />
          {uploading ? "Analyzing…" : "Add from documents…"}
        </button>
      </div>
      {memories.length > 0 && (
        <div className="px-3 pb-1.5 pt-2">
          <div className="relative">
            <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim">
              <PixelIcon name="search" size={11} />
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search memories"
              aria-label="Search memories by name or content"
              className="h-[30px] w-full rounded-[7px] border border-line bg-app pl-7 pr-2.5 text-[12.5px] text-ink outline-none placeholder:text-ink-dim focus:border-line-strong"
            />
          </div>
        </div>
      )}
      {uploadNote && (
        <div
          className={`px-4 py-1.5 text-[11.5px] leading-snug ${
            uploadNote.kind === "ok" ? "text-ok" : "text-danger"
          }`}
        >
          {uploadNote.text}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto py-2.5">
        {memories.length === 0 ? (
          <div className="px-4 py-2 text-xs leading-relaxed text-ink-dim">
            No memories yet. When you tell the agent something worth remembering (a
            stakeholder&apos;s preferences, a decision, a goal), it will save it here and have it
            available across sessions. You can also add memories from a document — a PRD, a
            strategy doc, meeting notes — with the button above.
          </div>
        ) : !hasMatches ? (
          <div className="px-4 py-3 text-xs leading-relaxed text-ink-dim">
            No memories match “{query.trim()}”.
          </div>
        ) : (
          TYPE_ORDER.filter((t) => grouped[t]?.length).map((t) => {
            const group = grouped[t] ?? [];
            // Collapse applies only in the normal browse view; during an active
            // search every matching category stays open so results are visible.
            const collapsed = !searching && memoryCollapsed[t];
            return (
              <div key={t} className="mb-3.5">
                <button
                  type="button"
                  disabled={searching}
                  onClick={() => toggleMemoryCategory(t)}
                  aria-expanded={!collapsed}
                  className="flex w-full items-center gap-1.5 px-4 pb-1 text-ink-dim transition-colors duration-100 hover:text-ink-muted disabled:cursor-default disabled:hover:text-ink-dim"
                >
                  <PixelIcon name={TYPE_ICONS[t]} size={10} />
                  <PxLabel>{TYPE_LABELS[t]}</PxLabel>
                  <span className="font-mono text-[10.5px] text-ink-dim">{group.length}</span>
                  {!searching && (
                    <span className="ml-auto text-ink-dim">
                      <PixelIcon name={collapsed ? "chevR" : "chevD"} size={9} />
                    </span>
                  )}
                </button>
                {!collapsed &&
                  group.map((r) => {
                  const active = r.id === selectedId;
                  return (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setSelectedId(active ? null : r.id)}
                      className={`mx-2 block w-[calc(100%-16px)] rounded-[7px] px-2.5 py-[7px] text-left transition-colors duration-100 ${
                        active ? "bg-surface shadow-card" : "hover:bg-raised"
                      }`}
                    >
                      <div className="truncate text-[12.5px] font-semibold text-ink">{r.title}</div>
                      {r.summary && (
                        <div className="mt-px line-clamp-2 text-[11.5px] text-ink-muted">
                          {r.summary}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })
        )}
      </div>

      {/* detail drawer pinned to the panel bottom */}
      {selectedId && (
        <div className="max-h-[46%] shrink-0 overflow-y-auto border-t border-line bg-surface">
          <div className="sticky top-0 flex items-center gap-2 border-b border-line-faint bg-surface px-3.5 pb-2 pt-2.5">
            <div className="min-w-0 flex-1 truncate text-[12.5px] font-bold text-ink">
              {detail?.title ?? "Loading…"}
            </div>
            <IconBtn
              icon="x"
              size={11}
              title="Close memory detail"
              onClick={() => setSelectedId(null)}
              className="!h-6 !w-6"
            />
          </div>
          <div className="px-3.5 pb-3.5 pt-2.5">
            {detailLoading && <div className="text-xs text-ink-dim">Loading…</div>}
            {detailError && <div className="text-xs text-danger">{detailError}</div>}
            {detail && !detailLoading && (
              <>
                {detail.tags && detail.tags.length > 0 && (
                  <MemoryTags tags={detail.tags} />
                )}
                {detail.summary && (
                  <div className="mb-2 text-[11.5px] italic text-ink-muted">{detail.summary}</div>
                )}
                <div className="markdown-body text-[12.5px] text-ink" style={{ lineHeight: 1.55 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                    {detail.body}
                  </ReactMarkdown>
                </div>
                <div className="mt-2.5 font-mono text-[10.5px] text-ink-dim">
                  Updated {new Date(detail.updated_at).toLocaleString()}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const BACKEND_LABELS: Record<string, string> = {
  google_docs: "Google Docs",
  local: "On this Mac",
};
const BACKEND_ORDER = ["google_docs", "local"];

function groupByBackend(docs: DocumentArtifact[]): Record<string, DocumentArtifact[]> {
  const out: Record<string, DocumentArtifact[]> = {};
  for (const d of docs) (out[d.backend] ||= []).push(d);
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

function DocumentsTab() {
  const documents = useChatStore((s) => s.documents);
  const documentsLoadedAt = useChatStore((s) => s.documentsLoadedAt);
  const setDocuments = useChatStore((s) => s.setDocuments);
  // Local files can only be opened from the desktop shell — set after mount
  // so server-rendered HTML matches the first client render.
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    setDesktop(isTauri());
  }, []);

  useEffect(() => {
    if (documentsLoadedAt !== 0) return;
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => console.error("[docs] failed to load:", err));
  }, [documentsLoadedAt, setDocuments]);

  const grouped = useMemo(() => groupByBackend(documents), [documents]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto py-2.5">
      {documents.length === 0 ? (
        <div className="px-4 py-2 text-xs leading-relaxed text-ink-dim">
          No documents yet. When a skill produces a deliverable (a PRD, stakeholder update,
          meeting agenda), it will land here.
        </div>
      ) : (
        BACKEND_ORDER.filter((b) => grouped[b]?.length).map((backend) => {
          const group = grouped[backend] ?? [];
          return (
            <div key={backend} className="mb-3.5">
              <div className="px-4 pb-1">
                <PxLabel>{BACKEND_LABELS[backend] ?? backend}</PxLabel>
              </div>
              {group.map((d) => (
                <div
                  key={`${d.backend}:${d.document_id}`}
                  className="mx-2 flex items-start gap-[9px] rounded-[7px] px-2.5 py-[7px] transition-colors duration-100 hover:bg-raised"
                >
                  <span className="mt-[2px] text-ink-dim">
                    <PixelIcon name="doc" size={12} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] font-semibold text-ink">{d.title}</div>
                    <div className="mt-px font-mono text-[10.5px] text-ink-dim">
                      {formatUpdated(d.updated_at)}
                    </div>
                  </div>
                  {d.url ? (
                    <ExternalLink
                      href={d.url}
                      className="shrink-0 rounded-[5px] border border-line bg-surface px-1.5 py-px text-[10.5px] font-semibold text-accent-text no-underline hover:bg-raised"
                      title="Open in Google Docs"
                    >
                      Open ↗
                    </ExternalLink>
                  ) : desktop && d.file_path ? (
                    <span className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => void openLocalPath(d.file_path as string)}
                        className="rounded-[5px] border border-line bg-surface px-1.5 py-px text-[10.5px] font-semibold text-accent-text hover:bg-raised"
                        title="Open in your default app"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => void revealInFolder(d.file_path as string)}
                        className="flex h-[18px] w-[18px] items-center justify-center rounded-[5px] border border-line bg-surface text-ink-muted hover:bg-raised hover:text-ink"
                        title="Show in Finder"
                      >
                        <PixelIcon name="folder" size={10} />
                      </button>
                    </span>
                  ) : (
                    <span
                      className="mt-[3px] shrink-0 font-mono text-[10px] text-ink-dim"
                      title={d.file_path ?? undefined}
                    >
                      local
                    </span>
                  )}
                </div>
              ))}
            </div>
          );
        })
      )}
    </div>
  );
}

// Merged Memory + Documents right panel with segmented tabs.
export function ContextPanel() {
  const contextTab = useUiStore((s) => s.contextTab);
  const setContextTab = useUiStore((s) => s.setContextTab);
  const setContextPanelOpen = useUiStore((s) => s.setContextPanelOpen);

  return (
    <aside className="flex h-full w-[312px] shrink-0 flex-col border-l border-line bg-panel">
      <div className="flex h-12 shrink-0 items-center gap-2 pl-4 pr-2">
        <PxLabel>Context</PxLabel>
        <span className="flex-1" />
        <IconBtn icon="x" size={11} title="Close context panel" onClick={() => setContextPanelOpen(false)} />
      </div>
      <Segmented
        className="mx-3"
        value={contextTab}
        onChange={setContextTab}
        options={[
          { key: "memory", label: "Memory", icon: "brain" },
          { key: "documents", label: "Documents", icon: "doc" },
        ]}
      />
      <div className="mt-1.5 flex min-h-0 flex-1 flex-col">
        {contextTab === "memory" ? <MemoryTab /> : <DocumentsTab />}
      </div>
    </aside>
  );
}
