"use client";
import { useState } from "react";
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

function statusColor(label: string): string {
  if (label === "running…") return "bg-amber-50 text-amber-700 border-amber-200";
  if (label === "error") return "bg-red-50 text-red-700 border-red-200";
  return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

function toolIcon(name: string): string {
  switch (name) {
    case "WebSearch":
      return "🔎";
    case "WebFetch":
      return "🌐";
    case "SaveMemory":
      return "💾";
    case "RecallMemory":
    case "SearchMemories":
      return "🧠";
    case "TodoWrite":
      return "✓";
    case "DraftMessage":
      return "✉️";
    case "QueryTickets":
      return "🎫";
    case "TimeCheck":
      return "🕒";
    default:
      return "⚙️";
  }
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
      if (typeof v === "string") {
        const s = v.length > 60 ? v.slice(0, 60) + "…" : v;
        return `${k}="${s}"`;
      }
      return `${k}=${JSON.stringify(v)}`;
    })
    .join(", ");
}

export function ToolCallBlock({ name, input, output, isError, status }: Props) {
  // Errored cards start expanded so the failure message is visible without
  // a click — users shouldn't have to hunt for why a tool broke.
  const defaultExpanded = isError || status === "error";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasOutput = output !== undefined && output !== "";
  const effectiveStatus = status ?? (hasOutput ? (isError ? "error" : "done") : "running");
  const label = statusLabel(effectiveStatus, hasOutput, !!isError);
  const colorClasses = statusColor(label);
  const compact = compactInput(input);
  const docUrl = extractGoogleDocUrl(output);

  return (
    <div
      className={`rounded-md border text-xs font-mono ${colorClasses} my-1.5`}
    >
      <div className="w-full flex items-center gap-2 px-3 py-1.5">
        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          className="flex-1 min-w-0 flex items-center gap-2 text-left hover:opacity-80 transition-opacity"
        >
          <span className="shrink-0">{toolIcon(name)}</span>
          <span className="font-semibold">{name}</span>
          {compact && (
            <span className="opacity-70 truncate min-w-0">{compact}</span>
          )}
        </button>
        {docUrl && (
          <ExternalLink
            href={docUrl}
            onClick={(e) => e.stopPropagation()}
            className="shrink-0 inline-flex items-center gap-1 rounded bg-white/80 ring-1 ring-inset ring-current/30 px-1.5 py-0.5 text-[10px] font-sans font-medium hover:bg-white"
            title="Open in Google Docs"
          >
            Open ↗
          </ExternalLink>
        )}
        <span className="shrink-0 text-[10px] uppercase tracking-wide">
          {label}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((x) => !x)}
          className="shrink-0 text-[10px] opacity-60 hover:opacity-100"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? "▾" : "▸"}
        </button>
      </div>
      {expanded && (
        <div className="px-3 pb-2 pt-0.5 space-y-2 border-t border-current/20">
          <div>
            <div className="text-[10px] uppercase tracking-wide opacity-60 mb-0.5">
              input
            </div>
            <pre className="whitespace-pre-wrap break-words bg-white/60 rounded px-2 py-1 text-[11px]">
              {JSON.stringify(input, null, 2)}
            </pre>
          </div>
          {hasOutput && (
            <div>
              <div className="text-[10px] uppercase tracking-wide opacity-60 mb-0.5">
                output
              </div>
              <pre className="whitespace-pre-wrap break-words bg-white/60 rounded px-2 py-1 text-[11px] max-h-64 overflow-y-auto">
                {output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
