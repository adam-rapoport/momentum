"use client";
import { useEffect, useState } from "react";
import { ExternalLink } from "@/components/ExternalLink";
import { DitherRule, PmLogo } from "@/components/pm";
import { isTauri } from "@/lib/desktop";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.3.0";
const CONTACT_EMAIL = "rapoport.apps@gmail.com";
const PORTFOLIO_URL = "https://dadvibecoding.vercel.app";

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
    ["Source", "github.com/adam-rapoport/momentum"],
  ];
  return (
    <div>
      <div className="mb-4 flex items-center gap-2.5">
        <PmLogo size={20} />
        <span className="font-pixel text-[13px] tracking-[0.06em] text-ink">MOMENTUM</span>
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
        are encrypted at rest, and Momentum talks directly to the providers you choose — nothing
        routes through a Momentum server.
      </p>

      <div className="mt-4 flex items-center gap-3 rounded-[10px] border border-line bg-raised px-3.5 py-3">
        <DevLogo size={30} />
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold text-ink">App by Adam Rapoport</div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <ExternalLink
              href={PORTFOLIO_URL}
              className="font-mono text-[11.5px] text-accent-text no-underline hover:underline"
            >
              {PORTFOLIO_URL.replace("https://", "")}
            </ExternalLink>
            <span className="text-[11px] text-ink-muted">·</span>
            <ExternalLink
              href={`mailto:${CONTACT_EMAIL}`}
              className="font-mono text-[11.5px] text-accent-text no-underline hover:underline"
            >
              {CONTACT_EMAIL}
            </ExternalLink>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Adam's developer mark — the pixel coffee cup from his app portfolio page
 *  (dadvibecoding.vercel.app). Used only in this credit card; the app mark
 *  everywhere else stays PmLogo. Colors are the portfolio's own brand greens,
 *  fixed across light/dark themes like any logo. */
function DevLogo({ size = 26 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      shapeRendering="crispEdges"
      aria-label="Adam Rapoport's developer logo — a pixel-art coffee cup"
    >
      <g fill="#0F9D63">
        <rect x="4" y="0" width="2" height="1" />
        <rect x="5" y="1" width="2" height="1" />
        <rect x="6" y="2" width="2" height="1" />
        <rect x="5" y="3" width="2" height="1" />
        <rect x="4" y="4" width="2" height="1" />
        <rect x="2" y="6" width="11" height="7" />
        <rect x="3" y="13" width="9" height="1" />
        <rect x="5" y="14" width="5" height="1" />
        <rect x="13" y="7" width="2" height="1" />
        <rect x="15" y="8" width="1" height="3" />
        <rect x="13" y="11" width="2" height="1" />
        <rect x="1" y="15" width="13" height="1" />
      </g>
      <g fill="#4CC896">
        <rect x="9" y="0" width="2" height="1" />
        <rect x="10" y="1" width="2" height="1" />
        <rect x="11" y="2" width="2" height="1" />
        <rect x="10" y="3" width="2" height="1" />
        <rect x="9" y="4" width="2" height="1" />
      </g>
      <g fill="#1C7D55">
        <rect x="3" y="7" width="9" height="2" />
        <rect x="3" y="16" width="9" height="1" />
      </g>
      <g fill="#5ED3A0">
        <rect x="4" y="10" width="1" height="3" />
      </g>
    </svg>
  );
}
