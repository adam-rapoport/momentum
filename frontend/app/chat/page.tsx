"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { ChatView } from "@/components/ChatView";
import { Header } from "@/components/Header";
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
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <h1 className="text-xl font-semibold mb-2">Welcome to pMomentum</h1>
            <p className="text-sm text-neutral-600">
              Your AI assistant for PM work. Click{" "}
              <span className="font-medium">&quot;+ New session&quot;</span> in the sidebar to start a
              conversation, or pick an existing one.
            </p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Header sessionId={sessionId} title={session?.title} />
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
