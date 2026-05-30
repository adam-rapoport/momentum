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
  const [displayName, setDisplayName] = useState<string>("You");

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
              return (
                <li key={s.id}>
                  <Link
                    href={`/chat?s=${s.id}`}
                    className={`block px-3 py-2 text-sm truncate border-l-2 ${
                      active
                        ? "border-neutral-900 bg-neutral-100 font-medium"
                        : "border-transparent text-neutral-700 hover:bg-neutral-50"
                    }`}
                  >
                    {s.title ?? "(untitled)"}
                  </Link>
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
