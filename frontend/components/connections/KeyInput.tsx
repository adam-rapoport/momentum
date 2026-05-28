"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { validateKeyFormat, type KeyFormatMeta } from "@/lib/providers";
import { Dot, HelpHint } from "./kit";

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
  const ref = useRef<HTMLInputElement>(null);
  const validation = useMemo(() => validateKeyFormat(provider, value), [provider, value]);

  useEffect(() => {
    if (autoFocus && ref.current) ref.current.focus();
  }, [autoFocus, provider]);

  const stateClass =
    validation.state === "valid" ? "valid" : validation.state === "invalid" ? "invalid" : "";

  return (
    <div>
      <label style={{ color: "var(--text-muted)" }} className="block text-[12.5px] font-medium mb-1.5">
        API key
        {provider?.keyHint && (
          <span style={{ color: "var(--text-dim)" }} className="mono text-[11.5px] ml-2 font-normal">
            {provider.keyHint}
          </span>
        )}
      </label>

      <div className="relative">
        <input
          ref={ref}
          className={`input ${stateClass}`}
          style={{ paddingRight: 64 }}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={provider?.keyPrefix ? `${provider.keyPrefix}...` : "Paste your key"}
          spellCheck={false}
          autoComplete="off"
        />
        <div className="absolute right-1.5 top-1.5">
          <button type="button" className="btn small ghost" onClick={() => setShow((s) => !s)}>
            {show ? "Hide" : "Show"}
          </button>
        </div>
      </div>

      <div className="mt-1.5 min-h-[18px] text-xs flex items-center gap-1.5">
        {validation.state === "valid" && (
          <>
            <Dot color="var(--success)" />
            <span style={{ color: "var(--success)" }}>{validation.message}</span>
          </>
        )}
        {validation.state === "invalid" && (
          <>
            <Dot color="var(--danger)" />
            <span style={{ color: "var(--danger)" }}>{validation.message}</span>
          </>
        )}
        {validation.state === "partial" && (
          <>
            <Dot color="var(--warn)" />
            <span style={{ color: "var(--text-muted)" }}>{validation.message}</span>
          </>
        )}
      </div>

      {showHelp && <HelpHint provider={provider} />}
    </div>
  );
}
