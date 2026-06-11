"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { ChatView } from "@/components/ChatView";
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
        <div className="flex flex-1 items-center justify-center">
          <div className="max-w-md text-center">
            <h1 className="mb-2 text-xl font-semibold text-ink">Welcome to pMomentum</h1>
            <p className="text-sm text-ink-muted">
              Your AI assistant for PM work. Click{" "}
              <span className="font-medium">&quot;New chat&quot;</span> in the sidebar to start a
              conversation, or pick an existing one.
            </p>
          </div>
        </div>
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
