"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { ChatView } from "@/components/ChatView";
import { HomeView } from "@/components/HomeView";
import { Toolbar } from "@/components/Toolbar";
import { useChatStore } from "@/lib/store";

function ChatInner() {
  // Sessions are addressed via ?s=<id> on this one static page (rather than a
  // /chat/<id> dynamic route) so the frontend can ship as static files for the
  // desktop build. useSearchParams requires a <Suspense> boundary under static
  // export — see the wrapper below.
  const sessionId = useSearchParams().get("s") ?? undefined;
  const session = useChatStore((s) => s.sessions.find((x) => x.id === sessionId));
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  useEffect(() => {
    setActiveSession(sessionId ?? null);
  }, [sessionId, setActiveSession]);

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
