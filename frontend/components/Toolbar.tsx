"use client";
import { Chip, IconBtn, StatusDot } from "@/components/pm";
import { isHeavyModel, modelShortName } from "@/lib/models";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/uiStore";
import type { SessionMetadata } from "@/lib/types";

interface ToolbarProps {
  sessionId?: string;
  title?: string | null;
}

// 48px top bar — replaces the old web-style Header. Doubles as a macOS
// titlebar drag region in the desktop build.
export function Toolbar({ sessionId, title }: ToolbarProps) {
  const wsConnected = useChatStore((s) => s.wsConnected);
  const totalCost = useChatStore((s) =>
    sessionId ? s.totalCostBySession[sessionId] : undefined,
  );
  // Fallback-outside-selector pattern: selector returns the session entry;
  // `?? undefined` keeps the reference stable so Zustand doesn't re-render.
  const session = useChatStore((s) =>
    sessionId ? s.sessions.find((x) => x.id === sessionId) : undefined,
  );
  const metadata: SessionMetadata | undefined = session?.session_metadata;
  const lastModel = useChatStore((s) =>
    sessionId ? s.lastModelBySession[sessionId] : undefined,
  );
  const contextPanelOpen = useUiStore((s) => s.contextPanelOpen);
  const setContextPanelOpen = useUiStore((s) => s.setContextPanelOpen);

  const skill = metadata?.active_skill;
  const phase = metadata?.active_skill_phase;
  const heavy = lastModel ? isHeavyModel(lastModel) : false;

  return (
    <header
      data-tauri-drag-region=""
      className="flex h-12 shrink-0 items-center gap-2.5 border-b border-line bg-app pl-5 pr-2.5"
    >
      <div data-tauri-drag-region="" className="flex min-w-0 flex-1 items-center gap-2.5">
        {title ? (
          <span className="truncate text-[13.5px] font-[650] text-ink">{title}</span>
        ) : (
          <span className="text-[13.5px] font-[650] text-ink-dim">New chat</span>
        )}
        {skill && (
          <Chip
            tone="accent"
            mono
            title={
              phase
                ? `Skill /${skill} active — ${phase} phase. /cancel-skill to exit.`
                : `Skill /${skill} active. /cancel-skill to exit.`
            }
          >
            <StatusDot tone="accent" size={5} pulse />
            /{skill}
            {phase ? ` · ${phase}` : ""}
          </Chip>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2.5">
        {lastModel && (
          <Chip mono tone={heavy ? "warn" : "dim"} title={`Last turn ran on ${lastModel}`}>
            <StatusDot tone={heavy ? "warn" : "dim"} size={5} />
            {modelShortName(lastModel)}
          </Chip>
        )}
        {totalCost !== undefined && (
          <span className="font-mono text-[11px] text-ink-dim" title="Session cost so far">
            ${Number(totalCost).toFixed(4)}
          </span>
        )}
        <span
          className="flex items-center gap-[5px]"
          title={
            wsConnected
              ? "Backend connected on localhost"
              : "Backend connection lost — reconnecting"
          }
        >
          <StatusDot tone={wsConnected ? "ok" : "danger"} size={6} />
          <span className="font-mono text-[10.5px] text-ink-dim">
            {wsConnected ? "local" : "offline"}
          </span>
        </span>
        <IconBtn
          icon="panel"
          title={contextPanelOpen ? "Hide context panel" : "Show context panel"}
          active={contextPanelOpen}
          onClick={() => setContextPanelOpen(!contextPanelOpen)}
        />
      </div>
    </header>
  );
}
