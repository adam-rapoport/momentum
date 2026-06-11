"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { ChatView } from "@/components/ChatView";
import { HomeView } from "@/components/HomeView";
import { Toolbar } from "@/components/Toolbar";
import { useChatStore } from "@/lib/store";
import { useUiStore, type SettingsPane } from "@/lib/uiStore";

const SETTINGS_PANES = new Set(["models", "integrations", "search", "profile", "about"]);

function ChatInner() {
  // Sessions are addressed via ?s=<id> on this one static page (rather than a
  // /chat/<id> dynamic route) so the frontend can ship as static files for the
  // desktop build. useSearchParams requires a <Suspense> boundary under static
  // export — see the wrapper below.
  const search = useSearchParams();
  const sessionId = search.get("s") ?? undefined;
  const session = useChatStore((s) => s.sessions.find((x) => x.id === sessionId));
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  useEffect(() => {
    setActiveSession(sessionId ?? null);
  }, [sessionId, setActiveSession]);

  // ?settings=<pane> opens the settings sheet (used by the old /settings
  // redirect stub and the Google OAuth return); ?google=connected|error
  // surfaces the OAuth result inside the Integrations pane.
  const settingsParam = search.get("settings");
  const googleParam = search.get("google");
  const googleReason = search.get("reason");
  useEffect(() => {
    if (!settingsParam) return;
    const ui = useUiStore.getState();
    const pane = SETTINGS_PANES.has(settingsParam) ? (settingsParam as SettingsPane) : undefined;
    if (googleParam === "connected") {
      ui.setGoogleBanner({
        kind: "success",
        message: "Google connected. Docs, Gmail, and Calendar are now available.",
      });
    } else if (googleParam === "error") {
      ui.setGoogleBanner({
        kind: "danger",
        message: `Google connection failed (${googleReason || "unknown"}).`,
      });
    }
    ui.openSettings(pane);
  }, [settingsParam, googleParam, googleReason]);

  if (!sessionId) {
    return (
      <>
        <Toolbar />
        <HomeView />
      </>
    );
  }

  return (
    <>
      <Toolbar sessionId={sessionId} title={session?.title} />
      <ChatView sessionId={sessionId} />
    </>
  );
}

export default function ChatIndex() {
  return (
    <Suspense fallback={null}>
      <ChatInner />
    </Suspense>
  );
}
