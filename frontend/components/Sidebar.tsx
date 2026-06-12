"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Btn, DitherRule, IconBtn, PixelIcon, PmLogo, PxLabel, StatusDot } from "@/components/pm";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/uiStore";
import type { Session } from "@/lib/types";

type RecencyGroup = "Today" | "Yesterday" | "This week" | "Earlier";
const GROUP_ORDER: RecencyGroup[] = ["Today", "Yesterday", "This week", "Earlier"];

function recencyGroup(iso: string): RecencyGroup {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "Earlier";
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday.getTime() - 86_400_000);
  const startOfWeek = new Date(startOfToday.getTime() - 6 * 86_400_000);
  if (d >= startOfToday) return "Today";
  if (d >= startOfYesterday) return "Yesterday";
  if (d >= startOfWeek) return "This week";
  return "Earlier";
}

function SessionRow({
  session,
  active,
  renaming,
  onStartRename,
  onCommitRename,
  onCancelRename,
  confirmingDelete,
  onDelete,
  onCancelDelete,
}: {
  session: Session;
  active: boolean;
  renaming: boolean;
  onStartRename: () => void;
  onCommitRename: (title: string) => void;
  onCancelRename: () => void;
  confirmingDelete: boolean;
  onDelete: () => void;
  onCancelDelete: () => void;
}) {
  const [draft, setDraft] = useState(session.title ?? "");
  // Re-seed the draft each time rename mode opens (the row stays mounted, so
  // the useState initializer alone would go stale after the first rename).
  useEffect(() => {
    if (renaming) setDraft(session.title ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renaming]);
  const hasSkill = Boolean(session.session_metadata?.active_skill);
  const title = session.title ?? "(untitled)";

  if (renaming) {
    return (
      <div className="px-2 py-[2px]">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => onCommitRename(draft)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onCommitRename(draft);
            if (e.key === "Escape") onCancelRename();
          }}
          aria-label="Session title"
          className="h-[30px] w-full rounded-[7px] border border-accent bg-surface px-2 text-[13px] text-ink shadow-[0_0_0_3px_var(--accent-tint)] outline-none"
        />
      </div>
    );
  }

  return (
    <div className="group/row relative px-2" onMouseLeave={onCancelDelete}>
      <Link
        href={`/chat?s=${session.id}`}
        className={`flex h-8 w-full items-center gap-2 rounded-[7px] border px-2.5 text-left transition-colors duration-100 ${
          active
            ? "border-line-faint bg-surface shadow-card"
            : "border-transparent hover:bg-raised"
        }`}
      >
        {hasSkill && <StatusDot tone="accent" size={6} />}
        <span
          className={`min-w-0 flex-1 truncate text-[13px] group-hover/row:pr-11 ${
            active ? "font-semibold text-ink" : "font-[450] text-ink-muted"
          }`}
        >
          {title}
        </span>
      </Link>
      <div
        className={`absolute right-3.5 top-1/2 hidden -translate-y-1/2 items-center gap-[2px] rounded-[6px] group-hover/row:flex ${
          active ? "bg-surface" : "bg-panel"
        }`}
      >
        <button
          type="button"
          title="Rename"
          aria-label={`Rename ${title}`}
          onClick={onStartRename}
          className="flex h-[22px] w-[22px] items-center justify-center rounded-[5px] text-ink-dim hover:bg-inset hover:text-ink"
        >
          <PixelIcon name="pencil" size={11} />
        </button>
        <button
          type="button"
          title={confirmingDelete ? "Click again to delete" : "Delete"}
          aria-label={`Delete ${title}`}
          onClick={onDelete}
          onBlur={onCancelDelete}
          className={`flex h-[22px] items-center justify-center gap-1 rounded-[5px] text-[10.5px] font-semibold ${
            confirmingDelete
              ? "px-1.5 bg-danger text-white"
              : "w-[22px] text-ink-dim hover:bg-danger-soft hover:text-danger"
          }`}
        >
          {confirmingDelete ? "Sure?" : <PixelIcon name="trash" size={11} />}
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  const router = useRouter();
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const sessions = useChatStore((s) => s.sessions);
  const setSessions = useChatStore((s) => s.setSessions);
  const upsertSession = useChatStore((s) => s.upsertSession);
  const removeSession = useChatStore((s) => s.removeSession);
  const profile = useUiStore((s) => s.profile);
  const loadProfile = useUiStore((s) => s.loadProfile);
  const openSettings = useUiStore((s) => s.openSettings);

  const [query, setQuery] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  // Theme is read from <html data-theme> after mount (set pre-paint by the
  // root layout script) — state here only drives the toggle icon.
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    api
      .listSessions()
      .then(setSessions)
      .catch((err) => console.error("failed to load sessions:", err));
  }, [setSessions]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

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

  async function commitRename(id: string, raw: string) {
    setRenamingId(null);
    const title = raw.trim();
    if (!title) return;
    try {
      const updated = await api.updateSession(id, { title });
      upsertSession(updated);
    } catch (err) {
      console.error("failed to rename session:", err);
    }
  }

  async function handleDelete(id: string) {
    if (confirmingDeleteId !== id) {
      setConfirmingDeleteId(id);
      return;
    }
    setConfirmingDeleteId(null);
    try {
      await api.archiveSession(id);
      removeSession(id);
      if (id === activeSessionId) router.push("/chat");
    } catch (err) {
      console.error("failed to delete session:", err);
    }
  }

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? sessions.filter((s) => (s.title ?? "").toLowerCase().includes(q))
      : sessions;
    const byGroup: Partial<Record<RecencyGroup, Session[]>> = {};
    for (const s of filtered) {
      (byGroup[recencyGroup(s.updated_at)] ||= []).push(s);
    }
    return GROUP_ORDER.filter((g) => byGroup[g]?.length).map((g) => ({
      name: g,
      items: byGroup[g] as Session[],
    }));
  }, [sessions, query]);

  const displayName = profile?.display_name ?? "You";

  return (
    <aside className="flex h-full w-[264px] shrink-0 flex-col border-r border-line bg-panel">
      {/* titlebar region — real traffic lights overlay here in the desktop build */}
      <div data-tauri-drag-region="" className="px-4 pb-2.5 pt-3.5">
        <div data-tauri-drag-region="" className="pm-traffic-spacer" />
        <div data-tauri-drag-region="" className="flex items-center gap-2">
          <PmLogo size={16} />
          <span className="font-pixel text-[11px] tracking-[0.06em] text-ink">PMOMENTUM</span>
        </div>
      </div>

      {/* new chat + search */}
      <div className="flex flex-col gap-2 px-3 pb-2.5">
        <Btn kind="primary" onClick={() => router.push("/chat")} className="w-full !justify-start gap-[9px]">
          <PixelIcon name="plus" size={12} />
          New chat
          <span className="ml-auto font-mono text-[11px] opacity-70">⌘N</span>
        </Btn>
        <div className="relative">
          <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim">
            <PixelIcon name="search" size={11} />
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            className="h-[30px] w-full rounded-[7px] border border-line bg-app pl-7 pr-2.5 text-[12.5px] text-ink outline-none placeholder:text-ink-dim focus:border-line-strong"
          />
        </div>
      </div>

      {/* sessions */}
      <div className="min-h-0 flex-1 overflow-y-auto pb-2">
        {groups.length === 0 && (
          <div className="px-5 py-4 text-[12.5px] text-ink-dim">
            {query ? "No chats match." : "No chats yet."}
          </div>
        )}
        {groups.map((g) => (
          <div key={g.name} className="mt-3">
            <div className="px-[18px] pb-1">
              <PxLabel>{g.name}</PxLabel>
            </div>
            <div className="flex flex-col gap-[1px]">
              {g.items.map((s) => (
                <SessionRow
                  key={s.id}
                  session={s}
                  active={s.id === activeSessionId}
                  renaming={renamingId === s.id}
                  onStartRename={() => {
                    setConfirmingDeleteId(null);
                    setRenamingId(s.id);
                  }}
                  onCommitRename={(title) => commitRename(s.id, title)}
                  onCancelRename={() => setRenamingId(null)}
                  confirmingDelete={confirmingDeleteId === s.id}
                  onDelete={() => handleDelete(s.id)}
                  onCancelDelete={() => {
                    if (confirmingDeleteId === s.id) setConfirmingDeleteId(null);
                  }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* footer */}
      <DitherRule />
      <div className="flex items-center gap-[9px] px-3 py-2.5">
        <span className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-accent-tint text-[11.5px] font-bold text-accent-text">
          {displayName.charAt(0).toUpperCase()}
        </span>
        <div
          className="min-w-0 flex-1"
          title="Everything stays on this Mac — chats and memories are private local files."
        >
          <div className="truncate text-[12.5px] font-semibold text-ink">{displayName}</div>
          <div className="font-mono text-[10.5px] text-ink-dim">local · private</div>
        </div>
        <IconBtn
          icon={theme === "dark" ? "sun" : "moon"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          onClick={toggleTheme}
        />
        <IconBtn icon="gear" title="Settings" onClick={() => openSettings()} />
      </div>
    </aside>
  );
}
