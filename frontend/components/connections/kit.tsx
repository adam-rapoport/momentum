"use client";
import { useState, type ReactNode } from "react";
import type { KeyFormatMeta, ProviderMeta } from "@/lib/providers";

export function Dot({ color, size = 6 }: { color: string; size?: number }) {
  return (
    <span
      style={{ width: size, height: size, background: color }}
      className="inline-block rounded-full shrink-0"
    />
  );
}

export function SectionHeader({
  eyebrow,
  title,
  sub,
  action,
}: {
  eyebrow?: string;
  title: string;
  sub?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-4">
      <div>
        {eyebrow && (
          <div
            style={{ color: "var(--text-dim)" }}
            className="text-[11px] font-semibold uppercase tracking-wider mb-1.5"
          >
            {eyebrow}
          </div>
        )}
        <div style={{ color: "var(--text)" }} className="text-xl font-semibold tracking-tight">
          {title}
        </div>
        {sub && (
          <div style={{ color: "var(--text-muted)" }} className="text-sm mt-1 max-w-xl">
            {sub}
          </div>
        )}
      </div>
      {action}
    </div>
  );
}

export function Banner({
  kind = "info",
  title,
  children,
  onDismiss,
}: {
  kind?: "info" | "warn" | "danger" | "success";
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
}) {
  const palette = {
    info: { bg: "var(--accent-tint)", fg: "var(--accent-text)" },
    warn: { bg: "var(--warn-soft)", fg: "var(--warn)" },
    danger: { bg: "var(--danger-soft)", fg: "var(--danger)" },
    success: { bg: "var(--success-soft)", fg: "var(--success)" },
  }[kind];
  return (
    <div
      style={{ background: palette.bg }}
      className="flex items-start gap-3 rounded-lg px-3.5 py-3"
    >
      <div className="mt-0.5">
        <Dot color={palette.fg} size={8} />
      </div>
      <div className="flex-1 min-w-0">
        {title && (
          <div style={{ color: palette.fg }} className="font-semibold text-[13px] mb-0.5">
            {title}
          </div>
        )}
        <div style={{ color: "var(--text)" }} className="text-[12.5px] leading-snug">
          {children}
        </div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{ color: palette.fg }}
          className="shrink-0 -mr-1 -mt-0.5 px-1 text-sm leading-none opacity-70 hover:opacity-100"
        >
          ✕
        </button>
      )}
    </div>
  );
}

export type ConnStatus = "ok" | "revoked" | "expired" | "limit" | "disconnected";

// Adaptive status: quiet when healthy, expands with a reason + one fix button
// when something is wrong.
export function StatusPill({
  status,
  account,
  lastUsed,
  error,
  onFix,
  fixLabel,
}: {
  status: ConnStatus;
  account?: string | null;
  lastUsed?: string | null;
  error?: string | null;
  onFix?: () => void;
  fixLabel?: string;
}) {
  if (status === "disconnected") {
    return (
      <span style={{ color: "var(--text-dim)" }} className="inline-flex items-center gap-2 text-[13px] whitespace-nowrap">
        <Dot color="var(--text-dim)" />
        Not connected
      </span>
    );
  }
  const isProblem = status !== "ok";
  const color =
    status === "ok" ? "var(--success)" : status === "limit" ? "var(--warn)" : "var(--danger)";
  const label =
    status === "ok"
      ? "Connected"
      : status === "limit"
      ? "Free-tier limit hit"
      : status === "expired"
      ? "Sign-in expired"
      : "Key was revoked";

  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      <div style={{ color: "var(--text)" }} className="flex items-center gap-2 text-[13px] flex-wrap">
        <span className="inline-flex items-center gap-2 whitespace-nowrap">
          <Dot color={color} />
          <span className="font-medium">{label}</span>
        </span>
        {account && (
          <span className="inline-flex items-center gap-2 whitespace-nowrap min-w-0">
            <span style={{ color: "var(--text-dim)" }}>·</span>
            <span style={{ color: "var(--text-muted)" }} className="mono">
              {account}
            </span>
          </span>
        )}
      </div>
      {(isProblem || lastUsed) && (
        <div style={{ color: "var(--text-muted)" }} className="text-xs pl-3.5">
          {isProblem && error ? (
            error
          ) : lastUsed ? (
            <>
              Last used <span style={{ color: "var(--text)" }}>{lastUsed}</span>
            </>
          ) : null}
        </div>
      )}
      {isProblem && onFix && (
        <div className="pl-3.5">
          <button
            className="btn small"
            style={{ borderColor: "var(--danger)", color: "var(--danger)", background: "transparent" }}
            onClick={onFix}
          >
            {fixLabel ??
              (status === "expired"
                ? "Re-authenticate"
                : status === "revoked"
                ? "Update key"
                : status === "limit"
                ? "Switch model"
                : "Fix")}
          </button>
        </div>
      )}
    </div>
  );
}

export function ProviderGlyph({ id }: { id: string }) {
  const letter: Record<string, string> = { groq: "G", google: "✦", openai: "O", tavily: "T", perplexity: "P" };
  const color: Record<string, string> = {
    groq: "#F47C2A",
    google: "#5279E0",
    openai: "#10A37F",
    tavily: "#3B7F6A",
    perplexity: "#20808D",
  };
  return (
    <span
      style={{ background: color[id] || "var(--bg-inset)" }}
      className="inline-flex items-center justify-center w-6 h-6 rounded-md text-white text-[13px] font-semibold mono"
    >
      {letter[id] || "·"}
    </span>
  );
}

export function ProviderTile({
  provider,
  selected,
  onSelect,
}: {
  provider: ProviderMeta;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(provider.id)}
      style={{
        borderColor: selected ? "var(--accent)" : "var(--border)",
        background: selected ? "var(--accent-tint)" : "var(--bg-elev)",
        boxShadow: selected ? "0 0 0 3px var(--accent-tint)" : "none",
      }}
      className="text-left p-3.5 rounded-[10px] border flex flex-col gap-2 min-h-[96px] transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <ProviderGlyph id={provider.id} />
          <span style={{ color: "var(--text)" }} className="font-semibold text-sm">
            {provider.name}
          </span>
        </div>
        {provider.badge && (
          <span className={`tag ${provider.badgeKind === "success" ? "success" : ""}`}>
            {provider.badge}
          </span>
        )}
      </div>
      <div style={{ color: "var(--text-muted)" }} className="text-[12.5px] leading-snug">
        {provider.description}
      </div>
      <div style={{ color: "var(--text-dim)" }} className="text-[11.5px] mt-auto">
        {provider.pricing}
      </div>
    </button>
  );
}

export function HelpHint({ provider }: { provider: KeyFormatMeta | null }) {
  const [open, setOpen] = useState(false);
  if (!provider?.helpUrl) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{ color: "var(--text-muted)" }}
        className="bg-transparent border-0 p-0 text-[12.5px] inline-flex items-center gap-1.5"
      >
        <span
          style={{ transform: open ? "rotate(90deg)" : "none" }}
          className="inline-block transition-transform"
        >
          ›
        </span>
        Where do I get a {provider.name} key?
      </button>
      {open && (
        <div
          style={{ background: "var(--bg-canvas)", borderColor: "var(--border-strong)", color: "var(--text-muted)" }}
          className="mt-2 px-3.5 py-3 border border-dashed rounded-lg text-[12.5px] leading-snug"
        >
          {provider.helpText}
          <br />
          <a
            href={provider.helpUrl}
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--text-dim)" }}
            className="mono text-[11.5px] underline"
          >
            {provider.helpUrl}
          </a>
        </div>
      )}
    </div>
  );
}
