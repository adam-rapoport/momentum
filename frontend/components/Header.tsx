"use client";
import { ModelBadge } from "@/components/ModelBadge";
import { SkillBadge } from "@/components/SkillBadge";
import { useChatStore } from "@/lib/store";
import type { SessionMetadata } from "@/lib/types";

interface HeaderProps {
  sessionId?: string;
  title?: string | null;
}

export function Header({ sessionId, title }: HeaderProps) {
  const wsConnected = useChatStore((s) => s.wsConnected);
  const totalCost = useChatStore((s) =>
    sessionId ? s.totalCostBySession[sessionId] : undefined,
  );
  // Fallback-outside-selector pattern: selector returns the session entry;
  // if absent, `?? undefined` provides a stable reference (undefined is
  // referentially equal to itself every render) so Zustand doesn't re-render.
  const session = useChatStore((s) =>
    sessionId ? s.sessions.find((x) => x.id === sessionId) : undefined,
  );
  const metadata: SessionMetadata | undefined = session?.session_metadata;
  const lastModel = useChatStore((s) =>
    sessionId ? s.lastModelBySession[sessionId] : undefined,
  );

  return (
    <header className="h-14 shrink-0 border-b border-neutral-200 bg-white px-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="text-sm font-semibold">pMomentum</div>
        {title && (
          <>
            <div className="text-neutral-300">›</div>
            <div className="text-sm text-neutral-600 truncate max-w-md">{title}</div>
          </>
        )}
        <SkillBadge metadata={metadata} />
        <ModelBadge model={lastModel} />
      </div>
      <div className="flex items-center gap-4 text-xs text-neutral-500">
        {totalCost !== undefined && <div>Cost: ${Number(totalCost).toFixed(6)}</div>}
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected ? "bg-green-500" : "bg-neutral-300"
            }`}
          />
          <span>{wsConnected ? "connected" : "disconnected"}</span>
        </div>
      </div>
    </header>
  );
}
