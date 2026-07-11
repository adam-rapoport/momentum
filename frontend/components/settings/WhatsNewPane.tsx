"use client";
import { useEffect } from "react";
import { CHANGELOG } from "@/lib/changelog";
import { useUiStore } from "@/lib/uiStore";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "";

export function WhatsNewPane() {
  const dismissUpdateNotice = useUiStore((s) => s.dismissUpdateNotice);

  // Viewing the pane counts as having seen the current version's news.
  useEffect(() => {
    dismissUpdateNotice();
  }, [dismissUpdateNotice]);

  return (
    <div className="flex flex-col gap-4">
      {CHANGELOG.map((entry) => (
        <div
          key={entry.version}
          className="rounded-[12px] border border-line bg-surface p-4 shadow-card"
        >
          <div className="flex items-baseline justify-between gap-3">
            <div className="text-[13.5px] font-semibold text-ink">{entry.title}</div>
            <div className="flex shrink-0 items-baseline gap-2">
              {entry.version === APP_VERSION && (
                <span className="rounded-full border border-line bg-raised px-2 py-0.5 text-[10.5px] font-medium text-accent-text">
                  current
                </span>
              )}
              <span className="font-mono text-[11.5px] text-ink-muted">v{entry.version}</span>
            </div>
          </div>
          <div className="mt-0.5 text-[11.5px] text-ink-dim">{entry.date}</div>
          <ul className="mt-2.5 flex list-disc flex-col gap-1.5 pl-4 text-[12.5px] leading-relaxed text-ink-muted">
            {entry.highlights.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
