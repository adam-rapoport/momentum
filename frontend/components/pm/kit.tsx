"use client";

import type { CSSProperties, ReactNode } from "react";
import { PixelIcon } from "./PixelIcon";
import type { PixelIconName } from "./bitmaps";

/* Shared primitives for the Graphite & Phosphor design system.
   Retro level is fixed at "subtle": pixel-font labels, 2px dither rules,
   round dots/avatars. Spec: docs/design/graphite-phosphor/README.md */

// Pixel-font section label — the retro "eyebrow". Never body text.
export function PxLabel({
  children,
  className = "",
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span
      className={`font-pixel font-bold uppercase whitespace-nowrap text-ink-muted ${className}`}
      style={{ fontSize: 10.5, letterSpacing: "0.005em", ...style }}
    >
      {children}
    </span>
  );
}

// Dithered horizontal rule — 2px checkerboard.
export function DitherRule({ className = "" }: { className?: string }) {
  return <div className={`dither h-[2px] opacity-80 ${className}`} style={{ color: "var(--border-strong)" }} />;
}

export function Btn({
  children,
  kind = "default",
  size = "md",
  type = "button",
  disabled,
  onClick,
  title,
  autoFocus,
  className = "",
  style,
}: {
  children: ReactNode;
  kind?: "default" | "primary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
  autoFocus?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  const sizes = {
    sm: "h-7 px-2.5 text-[12.5px] rounded-[8px]",
    md: "h-[34px] px-3.5 text-[13.5px] rounded-[8px]",
    lg: "h-[42px] px-5 text-[14.5px] rounded-[10px]",
  }[size];
  const kinds = {
    default: "bg-surface border-line-strong text-ink hover:bg-raised",
    primary: "bg-accent border-accent text-accent-fg font-semibold hover:brightness-[1.06]",
    ghost: "bg-transparent border-transparent text-ink-muted hover:bg-raised hover:text-ink",
    danger: "bg-transparent border-transparent text-danger hover:bg-danger-soft",
  }[kind];
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      autoFocus={autoFocus}
      className={`inline-flex items-center justify-center gap-[7px] font-medium whitespace-nowrap select-none border transition-colors duration-[120ms] disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:brightness-100 ${sizes} ${kinds} ${className}`}
      style={style}
    >
      {children}
    </button>
  );
}

// Icon-only button (toolbar, panel headers, micro-actions).
export function IconBtn({
  icon,
  size = 15,
  onClick,
  title,
  active,
  className = "",
}: {
  icon: PixelIconName;
  size?: number;
  onClick?: () => void;
  title?: string;
  active?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`inline-flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[7px] transition-colors duration-[120ms] ${
        active ? "bg-accent-tint text-accent-text" : "text-ink-muted hover:bg-raised hover:text-ink"
      } ${className}`}
    >
      <PixelIcon name={icon} size={size} />
    </button>
  );
}

export function Chip({
  children,
  tone = "dim",
  mono,
  title,
  className = "",
}: {
  children: ReactNode;
  tone?: "dim" | "accent" | "warn" | "ok" | "danger";
  mono?: boolean;
  title?: string;
  className?: string;
}) {
  const tones = {
    dim: "bg-raised text-ink-muted border-line-faint",
    accent: "bg-accent-tint text-accent-text border-transparent",
    warn: "bg-warn-soft text-warn border-transparent",
    ok: "bg-ok-soft text-ok border-transparent",
    danger: "bg-danger-soft text-danger border-transparent",
  }[tone];
  return (
    <span
      title={title}
      className={`inline-flex h-5 items-center gap-[5px] whitespace-nowrap rounded-full border px-2 text-[11px] font-medium ${
        mono ? "font-mono" : ""
      } ${tones} ${className}`}
      style={{ letterSpacing: "0.01em" }}
    >
      {children}
    </span>
  );
}

export function StatusDot({
  tone = "ok",
  size = 7,
  pulse,
}: {
  tone?: "ok" | "warn" | "danger" | "dim" | "accent";
  size?: number;
  pulse?: boolean;
}) {
  const colors = {
    ok: "var(--ok)",
    warn: "var(--warn)",
    danger: "var(--danger)",
    dim: "var(--text-dim)",
    accent: "var(--accent-bright)",
  }[tone];
  return (
    <span
      className={pulse ? "pm-pulse" : undefined}
      style={{ width: size, height: size, flexShrink: 0, display: "inline-block", borderRadius: 999, background: colors }}
    />
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd
      className="rounded-[4px] border border-line bg-raised px-1 font-mono text-ink-dim"
      style={{ fontSize: 10.5, borderBottomWidth: 2 }}
    >
      {children}
    </kbd>
  );
}

// Segmented control — inset track, surface active segment.
export function Segmented<K extends string>({
  options,
  value,
  onChange,
  className = "",
}: {
  options: { key: K; label: string; icon?: PixelIconName }[];
  value: K;
  onChange: (key: K) => void;
  className?: string;
}) {
  return (
    <div className={`flex rounded-[9px] bg-inset p-[3px] ${className}`}>
      {options.map((opt) => {
        const active = opt.key === value;
        return (
          <button
            key={opt.key}
            type="button"
            onClick={() => onChange(opt.key)}
            className={`flex h-[26px] flex-1 items-center justify-center gap-1.5 rounded-[7px] text-[12px] font-medium transition-colors duration-[120ms] ${
              active ? "bg-surface text-ink shadow-card" : "text-ink-muted hover:text-ink"
            }`}
          >
            {opt.icon && <PixelIcon name={opt.icon} size={11} />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// Alert banner — same interface as the legacy connections/kit Banner so the
// chat error taxonomy keeps working unchanged.
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
    success: { bg: "var(--ok-soft)", fg: "var(--ok)" },
  }[kind];
  return (
    <div style={{ background: palette.bg }} className="flex items-start gap-3 rounded-[10px] px-3.5 py-3">
      <div className="mt-1">
        <StatusDot tone={kind === "info" ? "accent" : kind === "success" ? "ok" : kind} size={8} />
      </div>
      <div className="min-w-0 flex-1">
        {title && (
          <div style={{ color: palette.fg }} className="mb-0.5 text-[13px] font-semibold">
            {title}
          </div>
        )}
        <div className="text-[12.5px] leading-snug text-ink">{children}</div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{ color: palette.fg }}
          className="-mr-1 -mt-0.5 shrink-0 px-1 text-sm leading-none opacity-70 hover:opacity-100"
        >
          ✕
        </button>
      )}
    </div>
  );
}
