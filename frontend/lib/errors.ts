// lib/api.ts already throws Error(<human-readable detail>) for every failed
// request — this just normalizes unknown throwables (non-Errors, DOMExceptions)
// to a display string for error banners.
export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
