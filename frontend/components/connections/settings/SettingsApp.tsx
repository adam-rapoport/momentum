"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, type ConnectionStatus, type KeyProvider } from "@/lib/api";
import { Wordmark } from "../Brand";
import { ThemeToggle } from "../ThemeToggle";
import { Banner } from "../kit";
import { AboutPane, AccountPane, IntegrationsPane, ModelsPane } from "./panes";

type Pane = "models" | "integrations" | "account" | "about";
type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

const NAV: { key: Pane; label: string }[] = [
  { key: "models", label: "Models" },
  { key: "integrations", label: "Integrations" },
  { key: "account", label: "Account" },
  { key: "about", label: "About" },
];

export function SettingsApp() {
  const [pane, setPane] = useState<Pane>("models");
  const [connections, setConnections] = useState<ConnMap>({});
  const search = useSearchParams();
  const googleFlag = search.get("google");

  const refresh = useCallback(() => {
    api
      .listConnections()
      .then((r) => {
        const map: ConnMap = {};
        for (const c of r.connections) map[c.provider] = c;
        setConnections(map);
      })
      .catch(() => undefined);
  }, []);

  useEffect(refresh, [refresh]);

  const banner =
    googleFlag === "connected"
      ? { kind: "success" as const, msg: "Google connected. Docs, Gmail, and Calendar are now available." }
      : googleFlag === "error"
      ? { kind: "danger" as const, msg: `Google connection failed (${search.get("reason") || "unknown"}).` }
      : null;

  return (
    <div className="c8-surface font-geist min-h-screen flex" style={{ background: "var(--bg-page)" }}>
      {/* sidebar */}
      <aside
        className="w-60 shrink-0 flex flex-col p-4"
        style={{ background: "var(--bg-canvas)", borderRight: "1px solid var(--border)" }}
      >
        <div className="px-1.5 mb-7">
          <Wordmark size={22} />
        </div>
        <Link href="/chat" className="btn ghost small justify-start mb-3">
          ← Back to chat
        </Link>
        <div
          style={{ color: "var(--text-dim)" }}
          className="text-[10.5px] font-semibold uppercase tracking-widest px-2.5 mb-2"
        >
          Settings
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((it) => (
            <button
              key={it.key}
              onClick={() => setPane(it.key)}
              style={{
                background: pane === it.key ? "var(--bg-elev-2)" : "transparent",
                color: pane === it.key ? "var(--text)" : "var(--text-muted)",
              }}
              className="text-left px-2.5 py-2 rounded-md text-[13.5px] font-medium"
            >
              {it.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between px-1 pt-4">
          <span style={{ color: "var(--text-dim)" }} className="text-[11.5px]">
            Local · single user
          </span>
          <ThemeToggle />
        </div>
      </aside>

      {/* content */}
      <main className="flex-1 overflow-y-auto px-12 py-8 min-w-0">
        <div className="max-w-3xl mx-auto">
          {banner && (
            <div className="mb-5">
              <Banner kind={banner.kind}>{banner.msg}</Banner>
            </div>
          )}
          {pane === "models" && <ModelsPane connections={connections} onChanged={refresh} />}
          {pane === "integrations" && <IntegrationsPane connections={connections} onChanged={refresh} />}
          {pane === "account" && <AccountPane onChanged={refresh} />}
          {pane === "about" && <AboutPane />}
        </div>
      </main>
    </div>
  );
}
