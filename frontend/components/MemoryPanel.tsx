"use client";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import type {
  MemoryRecordDetail,
  MemoryRecordSummary,
  MemoryType,
} from "@/lib/types";

const TYPE_LABELS: Record<MemoryType, string> = {
  stakeholder: "Stakeholders",
  decision: "Decisions",
  product: "Product",
  team: "Team",
  lessons: "Lessons",
  reference: "References",
};

const TYPE_ORDER: MemoryType[] = [
  "stakeholder",
  "decision",
  "product",
  "team",
  "lessons",
  "reference",
];

const TYPE_EMOJI: Record<MemoryType, string> = {
  stakeholder: "👤",
  decision: "✓",
  product: "📦",
  team: "👥",
  lessons: "💡",
  reference: "🔗",
};

function groupByType(
  records: MemoryRecordSummary[],
): Record<string, MemoryRecordSummary[]> {
  const out: Record<string, MemoryRecordSummary[]> = {};
  for (const r of records) {
    (out[r.type] ||= []).push(r);
  }
  return out;
}

export function MemoryPanel() {
  const memories = useChatStore((s) => s.memories);
  const memoriesLoadedAt = useChatStore((s) => s.memoriesLoadedAt);
  const setMemories = useChatStore((s) => s.setMemories);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MemoryRecordDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  // Initial load
  useEffect(() => {
    if (memoriesLoadedAt !== 0) return;
    api
      .listMemories()
      .then(setMemories)
      .catch((err) => console.error("[memory] failed to load:", err));
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
        if (cancelled) return;
        setDetail(d);
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

  const grouped = useMemo(() => groupByType(memories), [memories]);

  if (collapsed) {
    return (
      <div className="w-10 border-l border-neutral-200 bg-neutral-50 flex flex-col items-center py-3">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="text-neutral-600 hover:text-neutral-900 text-lg"
          title="Show memory panel"
        >
          🧠
        </button>
      </div>
    );
  }

  function handleRefresh() {
    api
      .listMemories()
      .then(setMemories)
      .catch((err) => console.error("[memory] refresh failed:", err));
  }

  return (
    <aside className="w-80 shrink-0 border-l border-neutral-200 bg-neutral-50 flex flex-col min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-base">🧠</span>
          <span className="font-semibold text-sm">Memory</span>
          <span className="text-xs text-neutral-500">{memories.length}</span>
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
        {memories.length === 0 ? (
          <div className="p-4 text-xs text-neutral-500 leading-relaxed">
            No memories yet. When you tell the agent something worth remembering
            (a stakeholder&apos;s preferences, a decision, a goal), it will save
            it here and have it available across sessions.
          </div>
        ) : (
          <div className="py-2">
            {TYPE_ORDER.filter((t) => grouped[t]?.length).map((t) => {
              const group = grouped[t] ?? [];
              return (
                <div key={t} className="mb-3">
                  <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-neutral-500 font-semibold flex items-center gap-1.5">
                    <span>{TYPE_EMOJI[t]}</span>
                    <span>{TYPE_LABELS[t]}</span>
                    <span className="text-neutral-400 font-normal">
                      ({group.length})
                    </span>
                  </div>
                  {group.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() =>
                        setSelectedId(selectedId === r.id ? null : r.id)
                      }
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-white transition-colors ${
                        selectedId === r.id ? "bg-white" : ""
                      }`}
                    >
                      <div className="font-medium text-neutral-900 truncate">
                        {r.title}
                      </div>
                      {r.summary && (
                        <div className="text-[11px] text-neutral-500 line-clamp-2 mt-0.5">
                          {r.summary}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedId && (
        <div className="border-t border-neutral-200 bg-white max-h-[45%] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-neutral-100 px-3 py-2 flex items-center justify-between">
            <div className="text-xs font-semibold truncate">
              {detail?.title ?? "Loading…"}
            </div>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="text-neutral-500 hover:text-neutral-900 text-xs px-1"
              title="Close"
            >
              ✕
            </button>
          </div>
          <div className="p-3">
            {detailLoading && (
              <div className="text-xs text-neutral-500">Loading…</div>
            )}
            {detailError && (
              <div className="text-xs text-red-600">{detailError}</div>
            )}
            {detail && !detailLoading && (
              <>
                {detail.tags && detail.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {detail.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] bg-neutral-100 text-neutral-700 px-1.5 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {detail.summary && (
                  <div className="text-[11px] text-neutral-600 italic mb-2">
                    {detail.summary}
                  </div>
                )}
                <div className="markdown-body text-xs">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {detail.body}
                  </ReactMarkdown>
                </div>
                <div className="mt-3 text-[10px] text-neutral-400">
                  Updated {new Date(detail.updated_at).toLocaleString()}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
