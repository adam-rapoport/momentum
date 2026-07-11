// Helpers for the Tauri desktop build. In web dev these all fall back to plain
// browser behaviour, so the same components run in both places.

/** True when running inside the Tauri desktop shell (vs a normal browser). */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/**
 * The per-launch backend auth token (see backend/app/security.py). The Tauri
 * shell generates it and exposes it via the `get_backend_token` command; api.ts
 * sends it as the X-Momentum-Token header and ws.ts as the `token` query
 * param. In web dev there is no shell and no token — resolves to null and the
 * backend skips the check. Cached: the token is fixed for the app's lifetime.
 */
function invokeCached<T>(cmd: string): () => Promise<T | null> {
  let promise: Promise<T | null> | null = null;
  return () => {
    if (!isTauri()) return Promise.resolve(null);
    if (!promise) {
      // Use the runtime-injected internals rather than @tauri-apps/api so web
      // builds don't need the package; same global isTauri() checks.
      const internals = (
        window as unknown as {
          __TAURI_INTERNALS__: { invoke: (cmd: string) => Promise<T> };
        }
      ).__TAURI_INTERNALS__;
      promise = internals.invoke(cmd).catch((err) => {
        console.error(`[desktop] ${cmd} failed:`, err);
        return null;
      });
    }
    return promise;
  };
}

const fetchToken = invokeCached<string>("get_backend_token");
const fetchPort = invokeCached<number>("get_backend_port");

export function getBackendToken(): Promise<string | null> {
  return fetchToken().then((t) => t || null);
}

/**
 * The loopback port the Tauri shell told the backend to bind. Usually 8000,
 * but the shell falls back to a free port when 8000 is taken (a dev uvicorn,
 * another app) — so api.ts/ws.ts must derive their base URLs from this rather
 * than the compile-time default. Null in web dev (no shell): callers fall
 * back to NEXT_PUBLIC_API_BASE / port 8000.
 */
export function getBackendPort(): Promise<number | null> {
  return fetchPort();
}

const DEFAULT_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const DEFAULT_WS_BASE =
  process.env.NEXT_PUBLIC_WS_BASE ?? "ws://localhost:8000";

export async function getApiBase(): Promise<string> {
  const port = await getBackendPort();
  return port ? `http://localhost:${port}` : DEFAULT_API_BASE;
}

export async function getWsBase(): Promise<string> {
  const port = await getBackendPort();
  return port ? `ws://localhost:${port}` : DEFAULT_WS_BASE;
}

/**
 * Open an external URL in the user's real browser.
 *
 * In the desktop app the UI lives in a webview that can't navigate to external
 * sites (e.g. a Google login page) — doing so silently does nothing. So we hand
 * the URL to the OS via Tauri's opener plugin. In web dev we just open a tab.
 */
// Raw plugin invoke via the runtime-injected internals — the same channel
// invokeCached uses for the token/port. Deliberately NOT the
// @tauri-apps/plugin-opener npm package: that route dynamic-imports a
// lazily-loaded chunk at click time, which is a silent single point of
// failure in a packaged build (observed in the first signed release: both
// About-pane links dead because the chunk never loaded, while raw invokes
// in the very same webview worked fine).
function invokeRaw<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  const internals = (
    window as unknown as {
      __TAURI_INTERNALS__: {
        invoke: (cmd: string, args?: Record<string, unknown>) => Promise<T>;
      };
    }
  ).__TAURI_INTERNALS__;
  return internals.invoke(cmd, args);
}

export async function openExternal(url: string): Promise<void> {
  if (isTauri()) {
    // Via the BACKEND, not Tauri IPC: webview->Rust invokes for URL-opening
    // were observed hanging without a response in packaged builds
    // (2026-07-04), while the webview->backend HTTP channel is exercised on
    // every API call and known-good. POST /system/open-url is scheme-
    // allowlisted and token-protected (see backend/app/api/system.py).
    const [base, token] = await Promise.all([getApiBase(), getBackendToken()]);
    const res = await fetch(`${base}/api/v1/system/open-url`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Momentum-Token": token } : {}),
      },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error(`open-url failed: ${res.status}`);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/**
 * Open a local file in its default app (desktop only — a browser can't touch
 * local paths, so callers should hide the affordance when !isTauri()).
 */
export async function openLocalPath(path: string): Promise<void> {
  if (!isTauri()) return;
  await invokeRaw("plugin:opener|open_path", { path });
}

/** Reveal a local file in Finder (desktop only). */
export async function revealInFolder(path: string): Promise<void> {
  if (!isTauri()) return;
  await invokeRaw("plugin:opener|reveal_item_in_dir", { path });
}

/**
 * Native "Save As" dialog (desktop only). Returns the chosen absolute path,
 * or null when the user cancels — or when we're in a browser, where callers
 * fall back to a normal download. Raw invoke on purpose; see the note above
 * invokeRaw for why the plugin npm packages are banned here.
 */
export async function saveFileDialog(
  defaultName: string,
  extension: string,
): Promise<string | null> {
  if (!isTauri()) return null;
  try {
    const path = await invokeRaw<string | null>("plugin:dialog|save", {
      options: {
        title: "Export document",
        defaultPath: defaultName,
        filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
      },
    });
    return path ?? null;
  } catch (err) {
    console.error("[desktop] save dialog failed:", err);
    return null;
  }
}
