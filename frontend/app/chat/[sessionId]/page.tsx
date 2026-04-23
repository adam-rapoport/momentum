"use client";
import { use } from "react";
import { ChatView } from "@/components/ChatView";
import { Header } from "@/components/Header";
import { useChatStore } from "@/lib/store";

export default function SessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const session = useChatStore((s) => s.sessions.find((x) => x.id === sessionId));
  return (
    <>
      <Header sessionId={sessionId} title={session?.title} />
      <ChatView sessionId={sessionId} />
    </>
  );
}
