"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink } from "@/components/ExternalLink";
import { StatusDot } from "@/components/pm";
import { validateKeyFormat, type KeyFormatMeta } from "@/lib/providers";

// Mono key input with live format validation (green = "format looks right")
// and a collapsible "where do I get a key?" hint. Real verification happens
// on save via the backend's validate-then-store.
export function KeyInput({
  provider,
  value,
  onChange,
  autoFocus,
  showHelp = true,
}: {
  provider: KeyFormatMeta | null;
  value: string;
  onChange: (v: string) => void;
  autoFocus?: boolean;
  showHelp?: boolean;
}) {
  const [show, setShow] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const validation = useMemo(() => validateKeyFormat(provider, value), [provider, value]);

  useEffect(() => {
    if (autoFocus && ref.current) ref.current.focus();
  }, [autoFocus, provider]);

  const borderClass =
    validation.state === "valid"
      ? "border-ok"
      : validation.state === "invalid"
        ? "border-danger"
        : "border-line-strong focus-within:border-accent";

  return (
    <div>
      <label className="mb-1.5 block text-[12.5px] font-medium text-ink-muted">
        API key
        {provider?.keyHint && (
          <span className="ml-2 font-mono text-[11.5px] font-normal text-ink-dim">
            {provider.keyHint}
          </span>
        )}
      </label>

      <div className={`flex h-10 items-center rounded-[8px] border bg-surface transition-colors ${borderClass}`}>
        <input
          ref={ref}
          className="h-full min-w-0 flex-1 bg-transparent px-3 font-mono text-[13px] text-ink outline-none placeholder:text-ink-dim focus-visible:shadow-none"
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={provider?.keyPrefix ? `${provider.keyPrefix}...` : "Paste your key"}
          spellCheck={false}
          autoComplete="off"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          className="mr-1.5 shrink-0 rounded-[6px] px-2 py-1 text-[11.5px] font-medium text-ink-muted hover:bg-raised hover:text-ink"
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>

      <div className="mt-1.5 flex min-h-[18px] items-center gap-1.5 text-xs">
        {validation.state === "valid" && (
          <>
            <StatusDot tone="ok" size={6} />
            <span className="text-ok">Format looks right — we&apos;ll verify on first use.</span>
          </>
        )}
        {validation.state === "invalid" && (
          <>
            <StatusDot tone="danger" size={6} />
            <span className="text-danger">{validation.message}</span>
          </>
        )}
        {validation.state === "partial" && (
          <>
            <StatusDot tone="warn" size={6} />
            <span className="text-ink-muted">{validation.message}</span>
          </>
        )}
      </div>

      {showHelp && provider?.helpUrl && (
        <div className="mt-1">
          <button
            type="button"
            onClick={() => setHelpOpen((o) => !o)}
            className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-muted hover:text-ink"
          >
            <span
              className="inline-block transition-transform duration-[120ms]"
              style={{ transform: helpOpen ? "rotate(90deg)" : "none" }}
            >
              ›
            </span>
            Where do I get a {provider.name} key?
          </button>
          {helpOpen && (
            <div className="mt-2 rounded-[8px] border border-dashed border-line-strong bg-raised px-3.5 py-3 text-[12.5px] leading-snug text-ink-muted">
              {provider.helpText}
              <br />
              <ExternalLink href={provider.helpUrl} className="font-medium text-accent-text underline">
                {provider.helpUrl.replace(/^https?:\/\//, "")} ↗
              </ExternalLink>
              <div className="mt-1.5 text-[12px] text-ink-dim">
                Stored encrypted on this Mac — never leaves it.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
