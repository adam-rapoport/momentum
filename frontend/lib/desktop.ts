// Helpers for the Tauri desktop build. In web dev these all fall back to plain
// browser behaviour, so the same components run in both places.

/** True when running inside the Tauri desktop shell (vs a normal browser). */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * Open an external URL in the user's real browser.
 *
 * In the desktop app the UI lives in a webview that can't navigate to external
 * sites (e.g. a Google login page) — doing so silently does nothing. So we hand
 * the URL to the OS via Tauri's opener plugin. In web dev we just open a tab.
 */
export async function openExternal(url: string): Promise<void> {
  if (isTauri()) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
