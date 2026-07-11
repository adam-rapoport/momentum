import { create } from "zustand";
import { api } from "@/lib/api";

// UI chrome state for the redesigned shell — kept separate from the chat data
// store (lib/store.ts) so the WS/data layer stays untouched.

export type ContextTab = "memory" | "documents";
export type SettingsPane =
  | "models"
  | "integrations"
  | "search"
  | "profile"
  | "help"
  | "whatsnew"
  | "about";

export interface UiProfile {
  display_name: string;
  workspace_name: string;
}

interface QueuedFirstMessage {
  sessionId: string;
  content: string;
  // Docs attached on the home screen, sent with the first message.
  attachments?: { id: string; filename: string }[];
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
  // Which Memory-pane categories are collapsed (keyed by memory type). Held in
  // the store so a collapse survives switching the Context panel's tabs.
  memoryCollapsed: Record<string, boolean>;
  // True on the first launch after an update (version changed since the user
  // last saw a "What's new" notice). Fresh installs never see it.
  updateNotice: boolean;

  setContextPanelOpen: (open: boolean) => void;
  dismissUpdateNotice: () => void;
  setContextTab: (tab: ContextTab) => void;
  toggleMemoryCategory: (type: string) => void;
  openSettings: (pane?: SettingsPane) => void;
  closeSettings: () => void;
  setGoogleBanner: (banner: GoogleBanner | null) => void;
  setProfile: (profile: UiProfile) => void;
  loadProfile: () => void;
  setQueuedFirstMessage: (q: QueuedFirstMessage | null) => void;
  restorePersisted: () => void;
}

const PANEL_KEY = "pmom-context-open";
const LAST_SEEN_VERSION_KEY = "pmom-last-seen-version";
const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "";

export const useUiStore = create<UiState>((set) => ({
  contextPanelOpen: true,
  contextTab: "memory",
  settingsOpen: false,
  settingsPane: "models",
  googleBanner: null,
  profile: null,
  queuedFirstMessage: null,
  memoryCollapsed: {},
  updateNotice: false,

  dismissUpdateNotice: () => {
    set({ updateNotice: false });
    try {
      if (APP_VERSION) localStorage.setItem(LAST_SEEN_VERSION_KEY, APP_VERSION);
    } catch {
      // ignore
    }
  },
  setContextPanelOpen: (open) => {
    set({ contextPanelOpen: open });
    try {
      localStorage.setItem(PANEL_KEY, open ? "1" : "0");
    } catch {
      // localStorage unavailable (shouldn't happen in the webview) — ignore
    }
  },
  setContextTab: (tab) => set({ contextTab: tab }),
  toggleMemoryCategory: (type) =>
    set((s) => ({
      memoryCollapsed: { ...s.memoryCollapsed, [type]: !s.memoryCollapsed[type] },
    })),
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
    try {
      if (APP_VERSION) {
        const seen = localStorage.getItem(LAST_SEEN_VERSION_KEY);
        if (seen === null) {
          // Fresh install (or first run on this build) — nothing is "new".
          localStorage.setItem(LAST_SEEN_VERSION_KEY, APP_VERSION);
        } else if (seen !== APP_VERSION) {
          set({ updateNotice: true });
        }
      }
    } catch {
      // ignore
    }
  },
}));
