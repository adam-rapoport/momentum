"use client";
import { useState } from "react";
import { PixelIcon, PxLabel, StatusDot, type PixelIconName } from "@/components/pm";
import { ExternalLink } from "./ExternalLink";

interface Props {
  name: string;
  input: Record<string, unknown>;
  output?: string;
  isError?: boolean;
  status?: "running" | "done" | "error";
}

function statusLabel(status: Props["status"], hasOutput: boolean, isError: boolean): string {
  if (status === "running" || (!hasOutput && status !== "error")) return "running…";
  if (status === "error" || isError) return "error";
  return "done";
}

const TOOL_ICONS: Record<string, PixelIconName> = {
  WebSearch: "globe",
  WebFetch: "globe",
  SaveMemory: "floppy",
  RecallMemory: "brain",
  SearchMemories: "brain",
  TodoWrite: "check",
  DraftMessage: "mail",
  SendEmail: "mail",
  DraftEmail: "mail",
  ListEmails: "mail",
  ReadEmail: "mail",
  QueryTickets: "tag",
  TimeCheck: "clock",
  CreateDocument: "doc",
  UpdateDocument: "doc",
  ReadDocument: "doc",
  WriteDocument: "doc",
  AwaitReview: "clock",
  ListCalendarEvents: "calendar",
  FindAvailability: "calendar",
  CreateCalendarEvent: "calendar",
};

function toolIcon(name: string): PixelIconName {
  return TOOL_ICONS[name] ?? "gear";
}

// Match the first Google Docs URL in a tool result so we can surface an
// "Open" link on the collapsed header — saves the user from having to
// expand the card + scroll the output to find it.
const GOOGLE_DOC_URL_RE = /https:\/\/docs\.google\.com\/document\/d\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_?=&%.#-]*)?/;

function extractGoogleDocUrl(output: string | undefined): string | null {
  if (!output) return null;
  const match = output.match(GOOGLE_DOC_URL_RE);
  return match ? match[0] : null;
}

function compactInput(input: Record<string, unknown>): string {
  const entries = Object.entries(input).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => {
      const raw = typeof v === "string" ? v : JSON.stringify(v);
      const s = raw.length > 48 ? raw.slice(0, 48) + "…" : raw;
      return `${k}: ${s}`;
    })
    .join(" · ");
}

export function ToolCallBlock({ name, input, output, isError, status }: Props) {
  // Errored cards start expanded so the failure message is visible without
  // a click — users shouldn't have to hunt for why a tool broke.
  const defaultExpanded = isError || status === "error";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasOutput = output !== undefined && output !== "";
  const effectiveStatus = status ?? (hasOutput ? (isError ? "error" : "done") : "running");
  const label = statusLabel(effectiveStatus, hasOutput, !!isError);
  const dotTone = label === "running…" ? "warn" : label === "error" ? "danger" : "ok";
  const compact = compactInput(input);
  const docUrl = extractGoogleDocUrl(output);

  return (
    <div className="my-1.5 rounded-[9px] border border-line-faint bg-raised font-mono text-[11.5px] text-ink">
      <div className="flex w-full items-center gap-2 px-3 py-[7px]">
        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left transition-opacity hover:opacity-80"
        >
          <span className="shrink-0 text-ink-muted">
            <PixelIcon name={toolIcon(name)} size={12} />
          </span>
          <span className="shrink-0 font-semibold">{name}</span>
          {compact && <span className="min-w-0 truncate text-ink-dim">{compact}</span>}
        </button>
        {docUrl && (
          <ExternalLink
            href={docUrl}
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 rounded-[5px] border border-line bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-accent-text hover:bg-surface/60"
            title="Open in Google Docs"
          >
            Open ↗
          </ExternalLink>
        )}
        <StatusDot tone={dotTone} size={6} pulse={label === "running…"} />
        <span
          className={`shrink-0 text-[10px] uppercase tracking-wide ${
            dotTone === "warn" ? "text-warn" : dotTone === "danger" ? "text-danger" : "text-ok"
          }`}
        >
          {label}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          className="shrink-0 text-ink-dim transition-transform duration-[120ms] hover:text-ink"
          style={{ transform: expanded ? "rotate(90deg)" : "none" }}
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <PixelIcon name="chevR" size={11} />
        </button>
      </div>
      {expanded && (
        <div className="space-y-2 border-t border-line-faint px-3 pb-2.5 pt-1.5">
          <div>
            <div className="mb-1">
              <PxLabel style={{ fontSize: 9.5 }}>Input</PxLabel>
            </div>
            <pre className="whitespace-pre-wrap break-words rounded-[6px] bg-inset px-2 py-1.5 text-[11px]">
              {JSON.stringify(input, null, 2)}
            </pre>
          </div>
          {hasOutput && (
            <div>
              <div className="mb-1">
                <PxLabel style={{ fontSize: 9.5 }}>Output</PxLabel>
              </div>
              <pre className="max-h-[180px] overflow-y-auto whitespace-pre-wrap break-words rounded-[6px] bg-inset px-2 py-1.5 text-[11px]">
                {output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
