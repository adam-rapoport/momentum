"use client";
import { useCallback, useEffect, useState } from "react";
import { Banner, IconBtn, PixelIcon, PxLabel, type PixelIconName } from "@/components/pm";
import { api, type ConnectionStatus, type KeyProvider } from "@/lib/api";
import { useUiStore, type SettingsPane } from "@/lib/uiStore";
import { AboutPane } from "./AboutPane";
import { IntegrationsPane } from "./IntegrationsPane";
import { ModelsPane } from "./ModelsPane";
import { ProfilePane } from "./ProfilePane";
import { SearchPane } from "./SearchPane";

type ConnMap = Partial<Record<KeyProvider, ConnectionStatus>>;

const NAV: { key: SettingsPane; label: string; icon: PixelIconName }[] = [
  { key: "models", label: "Models", icon: "bolt" },
  { key: "integrations", label: "Integrations", icon: "plug" },
  { key: "search", label: "Web search", icon: "globe" },
  { key: "profile", label: "Profile", icon: "user" },
  { key: "about", label: "About", icon: "box" },
];

// Settings as a modal sheet over the chat (replaces the old /settings page).
export function SettingsSheet() {
  const open = useUiStore((s) => s.settingsOpen);
  const pane = useUiStore((s) => s.settingsPane);
  const openSettings = useUiStore((s) => s.openSettings);
  const closeSettings = useUiStore((s) => s.closeSettings);

  const [connections, setConnections] = useState<ConnMap>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .listConnections()
      .then((r) => {
        const map: ConnMap = {};
        for (const c of r.connections) map[c.provider] = c;
        setConnections(map);
        setLoadError(null);
      })
      .catch((e) => {
        // Don't swallow this: against a dead backend everything would render
        // as "Not connected", which looks like the user's keys vanished.
        setLoadError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeSettings();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, closeSettings]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: "rgba(10, 12, 14, 0.45)", backdropFilter: "blur(3px)" }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) closeSettings();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
    >
      <div className="flex h-[560px] max-h-full w-[820px] max-w-full overflow-hidden rounded-[14px] border border-line bg-app shadow-pop">
        {/* nav rail */}
        <aside className="flex w-[186px] shrink-0 flex-col border-r border-line bg-panel p-3">
          <div className="px-2.5 pb-2.5 pt-1.5">
            <PxLabel>Settings</PxLabel>
          </div>
          <nav className="flex flex-col gap-[2px]">
            {NAV.map((item) => {
              const active = pane === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => openSettings(item.key)}
                  className={`flex h-8 items-center gap-2.5 rounded-[7px] border px-2.5 text-left text-[13px] transition-colors duration-100 ${
                    active
                      ? "border-line-faint bg-surface font-semibold text-ink shadow-card"
                      : "border-transparent font-medium text-ink-muted hover:bg-raised"
                  }`}
                >
                  <PixelIcon name={item.icon} size={12} />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* content */}
        <main className="relative min-w-0 flex-1 overflow-y-auto px-7 py-6">
          <div className="absolute right-3 top-3">
            <IconBtn icon="x" size={11} title="Close settings" onClick={closeSettings} />
          </div>
          {loadError && (
            <div className="mb-4">
              <Banner kind="danger" title="Couldn't load your connections">
                {loadError}{" "}
                <button type="button" onClick={refresh} className="font-medium underline">
                  Retry
                </button>
              </Banner>
            </div>
          )}
          {pane === "models" && <ModelsPane connections={connections} onChanged={refresh} />}
          {pane === "integrations" && <IntegrationsPane />}
          {pane === "search" && <SearchPane connections={connections} onChanged={refresh} />}
          {pane === "profile" && <ProfilePane onChanged={refresh} />}
          {pane === "about" && <AboutPane />}
        </main>
      </div>
    </div>
  );
}
