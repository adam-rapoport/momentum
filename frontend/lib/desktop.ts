// Helpers for the Tauri desktop build. In web dev these all fall back to plain
// browser behaviour, so the same components run in both places.

/** True when running inside the Tauri desktop shell (vs a normal browser). */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * The per-launch backend auth token (see backend/app/security.py). The Tauri
 * shell generates it and exposes it via the `get_backend_token` command; api.ts
 * sends it as the X-PMomentum-Token header and ws.ts as the `token` query
 * param. In web dev there is no shell and no token — resolves to null and the
 * backend skips the check. Cached: the token is fixed for the app's lifetime.
 */
let tokenPromise: Promise<string | null> | null = null;

export function getBackendToken(): Promise<string | null> {
  if (!isTauri()) return Promise.resolve(null);
  if (!tokenPromise) {
    // Use the runtime-injected internals rather than @tauri-apps/api so web
    // builds don't need the package; this is the same global isTauri() checks.
    const internals = (
      window as unknown as {
        __TAURI_INTERNALS__: {
          invoke: (cmd: string) => Promise<string>;
        };
      }
    ).__TAURI_INTERNALS__;
    tokenPromise = internals
      .invoke("get_backend_token")
      .then((t) => t || null)
      .catch((err) => {
        console.error("[desktop] failed to fetch backend token:", err);
        return null;
      });
  }
  return tokenPromise;
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
