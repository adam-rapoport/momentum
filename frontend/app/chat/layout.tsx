"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BootGate } from "@/components/BootGate";
import { ContextPanel } from "@/components/ContextPanel";
import { Sidebar } from "@/components/Sidebar";
import { WsProvider } from "@/components/WsProvider";
import { useUiStore } from "@/lib/uiStore";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const contextPanelOpen = useUiStore((s) => s.contextPanelOpen);
  const restorePersisted = useUiStore((s) => s.restorePersisted);

  // Restore persisted UI prefs (context panel open/closed) after mount —
  // module init must not touch localStorage (SSR prerender).
  useEffect(() => {
    restorePersisted();
  }, [restorePersisted]);

  // ⌘N / Ctrl+N — new chat (home state; the session is created on first send).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        router.push("/chat");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  // BootGate waits for the backend to be ready (showing a loading screen) and
  // routes first-run users to onboarding, so everything below it — the
  // WebSocket connection and all the on-mount data fetches — only runs once
  // the backend is actually serving.
  return (
    <BootGate>
      <WsProvider>
        <div className="flex h-screen overflow-hidden bg-app">
          <Sidebar />
          <main className="flex min-w-0 flex-1 flex-col">{children}</main>
          {contextPanelOpen && <ContextPanel />}
        </div>
      </WsProvider>
    </BootGate>
  );
}
