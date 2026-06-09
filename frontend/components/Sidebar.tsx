"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";

export function Sidebar() {
  const router = useRouter();
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const sessions = useChatStore((s) => s.sessions);
  const setSessions = useChatStore((s) => s.setSessions);
  const upsertSession = useChatStore((s) => s.upsertSession);
  const removeSession = useChatStore((s) => s.removeSession);
  const [displayName, setDisplayName] = useState<string>("You");
  // Inline rename state: which session is being renamed, and the draft title.
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  // Two-step delete: first click arms ("Sure?"), second click archives.
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    api
      .listSessions()
      .then(setSessions)
      .catch((err) => console.error("failed to load sessions:", err));
  }, [setSessions]);

  useEffect(() => {
    api
      .getProfile()
      .then((p) => {
        if (p.display_name?.trim()) setDisplayName(p.display_name.trim());
      })
      .catch((err) => console.error("failed to load profile:", err));
  }, []);

  async function handleNewSession() {
    try {
      const s = await api.createSession({});
      upsertSession(s);
      router.push(`/chat?s=${s.id}`);
    } catch (err) {
      console.error("failed to create session:", err);
    }
  }

  function startRename(id: string, currentTitle: string | null) {
    setConfirmingDeleteId(null);
    setRenamingId(id);
    setDraftTitle(currentTitle ?? "");
  }

  async function commitRename() {
    const id = renamingId;
    const title = draftTitle.trim();
    setRenamingId(null);
    if (!id || !title) return;
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

  return (
    <aside className="w-64 shrink-0 border-r border-neutral-200 bg-white flex flex-col">
      <div className="p-3 border-b border-neutral-200">
        <button
          onClick={handleNewSession}
          className="w-full rounded-md bg-neutral-900 text-white text-sm font-medium py-2 hover:bg-neutral-800 transition-colors"
        >
          + New session
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-3 text-sm text-neutral-500">
            No sessions yet. Click &quot;New session&quot; to start.
          </div>
        ) : (
          <ul className="py-1">
            {sessions.map((s) => {
              const active = s.id === activeSessionId;
              if (s.id === renamingId) {
                return (
                  <li key={s.id} className="px-3 py-1.5">
                    <input
                      autoFocus
                      value={draftTitle}
                      onChange={(e) => setDraftTitle(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename();
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      aria-label="Session title"
                      className="w-full rounded border border-neutral-300 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
                    />
                  </li>
                );
              }
              return (
                <li key={s.id} className="group relative">
                  <Link
                    href={`/chat?s=${s.id}`}
                    className={`block px-3 py-2 pr-16 text-sm truncate border-l-2 ${
                      active
                        ? "border-neutral-900 bg-neutral-100 font-medium"
                        : "border-transparent text-neutral-700 hover:bg-neutral-50"
                    }`}
                  >
                    {s.title ?? "(untitled)"}
                  </Link>
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => startRename(s.id, s.title)}
                      title="Rename"
                      aria-label={`Rename session ${s.title ?? "(untitled)"}`}
                      className="rounded px-1 py-0.5 text-xs text-neutral-500 hover:bg-neutral-200 hover:text-neutral-900"
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(s.id)}
                      onBlur={() => setConfirmingDeleteId(null)}
                      title={
                        confirmingDeleteId === s.id
                          ? "Click again to delete"
                          : "Delete"
                      }
                      aria-label={`Delete session ${s.title ?? "(untitled)"}`}
                      className={`rounded px-1 py-0.5 text-xs ${
                        confirmingDeleteId === s.id
                          ? "bg-red-600 text-white hover:bg-red-700"
                          : "text-neutral-500 hover:bg-neutral-200 hover:text-red-600"
                      }`}
                    >
                      {confirmingDeleteId === s.id ? "Sure?" : "🗑"}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="border-t border-neutral-200 p-3 flex items-center justify-between text-xs text-neutral-500">
        <span>Signed in as {displayName}</span>
        <Link
          href="/settings"
          className="rounded px-2 py-1 text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900"
          title="Settings"
        >
          Settings
        </Link>
      </div>
    </aside>
  );
}
