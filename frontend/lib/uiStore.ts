import { create } from "zustand";
import { api } from "@/lib/api";

// UI chrome state for the redesigned shell — kept separate from the chat data
// store (lib/store.ts) so the WS/data layer stays untouched.

export type ContextTab = "memory" | "documents";
export type SettingsPane = "models" | "integrations" | "search" | "profile" | "help" | "about";

export interface UiProfile {
  display_name: string;
  workspace_name: string;
}

interface QueuedFirstMessage {
  sessionId: string;
  content: string;
}

export interface GoogleBanner {
  kind: "success" | "danger";
  message: string;
}

interface UiState {
  contextPanelOpen: boolean;
  contextTab: ContextTab;
  settingsOpen: boolean;
  settingsPane: SettingsPane;
  // One-shot banner shown in the Integrations pane after an OAuth return
  // (web dev only — the flow lands on /settings?google=… and redirects here).
  googleBanner: GoogleBanner | null;
  profile: UiProfile | null;
  // Message typed on the home screen, sent once the new session's ChatView
  // has finished its initial load (avoids the mount-fetch clobbering the
  // optimistic user bubble).
  queuedFirstMessage: QueuedFirstMessage | null;

  setContextPanelOpen: (open: boolean) => void;
  setContextTab: (tab: ContextTab) => void;
  openSettings: (pane?: SettingsPane) => void;
  closeSettings: () => void;
  setGoogleBanner: (banner: GoogleBanner | null) => void;
  setProfile: (profile: UiProfile) => void;
  loadProfile: () => void;
  setQueuedFirstMessage: (q: QueuedFirstMessage | null) => void;
  restorePersisted: () => void;
}

const PANEL_KEY = "pmom-context-open";

export const useUiStore = create<UiState>((set) => ({
  contextPanelOpen: true,
  contextTab: "memory",
  settingsOpen: false,
  settingsPane: "models",
  googleBanner: null,
  profile: null,
  queuedFirstMessage: null,

  setContextPanelOpen: (open) => {
    set({ contextPanelOpen: open });
    try {
      localStorage.setItem(PANEL_KEY, open ? "1" : "0");
    } catch {
      // localStorage unavailable (shouldn't happen in the webview) — ignore
    }
  },
  setContextTab: (tab) => set({ contextTab: tab }),
  openSettings: (pane) => set((s) => ({ settingsOpen: true, settingsPane: pane ?? s.settingsPane })),
  closeSettings: () => set({ settingsOpen: false, googleBanner: null }),
  setGoogleBanner: (banner) => set({ googleBanner: banner }),
  setProfile: (profile) => set({ profile }),
  loadProfile: () => {
    api
      .getProfile()
      .then((p) =>
        set({
          profile: {
            display_name: p.display_name?.trim() || "You",
            workspace_name: p.workspace_name?.trim() || "My Workspace",
          },
        }),
      )
      .catch((err) => console.error("failed to load profile:", err));
  },
  setQueuedFirstMessage: (q) => set({ queuedFirstMessage: q }),
  // Called once after mount (client only) — module init must stay SSR-safe.
  restorePersisted: () => {
    try {
      const saved = localStorage.getItem(PANEL_KEY);
      if (saved !== null) set({ contextPanelOpen: saved === "1" });
    } catch {
      // ignore
    }
  },
}));
