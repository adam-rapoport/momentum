"use client";
import { useEffect, useState } from "react";
import { ExternalLink } from "@/components/ExternalLink";
import { DitherRule, PmLogo } from "@/components/pm";
import { isTauri } from "@/lib/desktop";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0";
const CONTACT_EMAIL = "rapoport.apps@gmail.com";

export function AboutPane() {
  const [shell, setShell] = useState("web");
  useEffect(() => {
    setShell(isTauri() ? "desktop (Tauri)" : "web (dev)");
  }, []);

  const lines: [string, string][] = [
    ["Version", APP_VERSION],
    ["Shell", shell],
    ["Backend", "FastAPI · localhost"],
    ["Data", "SQLite + local files · keys encrypted (Fernet)"],
    ["Source", "github.com/adam-rapoport/pmomentum"],
  ];
  return (
    <div>
      <div className="mb-4 flex items-center gap-2.5">
        <PmLogo size={20} />
        <span className="font-pixel text-[13px] tracking-[0.06em] text-ink">PMOMENTUM</span>
      </div>

      <div className="rounded-[12px] border border-line bg-surface p-4 shadow-card">
        {lines.map(([k, v], i) => (
          <div
            key={k}
            className={`flex justify-between gap-4 py-2 text-[12.5px] ${
              i < lines.length - 1 ? "border-b border-line-faint" : ""
            }`}
          >
            <span className="text-ink-muted">{k}</span>
            <span className="text-right font-mono text-[12px] text-ink">{v}</span>
          </div>
        ))}
      </div>

      <div className="my-4">
        <DitherRule />
      </div>

      <p className="text-[12.5px] leading-relaxed text-ink-muted">
        An AI agent for product management work, running entirely on your machine. Your API keys
        are encrypted at rest, and pMomentum talks directly to the providers you choose — nothing
        routes through a pMomentum server.
      </p>

      <div className="mt-4 flex items-center gap-3 rounded-[10px] border border-line bg-raised px-3.5 py-3">
        <PmLogo size={26} />
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold text-ink">App by Adam Rapoport</div>
          <ExternalLink
            href={`mailto:${CONTACT_EMAIL}`}
            className="font-mono text-[11.5px] text-accent-text no-underline hover:underline"
          >
            {CONTACT_EMAIL}
          </ExternalLink>
        </div>
      </div>
    </div>
  );
}
