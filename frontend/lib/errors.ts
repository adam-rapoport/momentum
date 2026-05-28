// Our fetch helper (lib/api.ts) throws Error("<status> <statusText>: <body>").
// When the body is a FastAPI error it's {"detail": "..."} — surface just that.
export function extractDetail(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  const brace = msg.indexOf("{");
  if (brace >= 0) {
    try {
      const parsed = JSON.parse(msg.slice(brace));
      if (parsed?.detail) return String(parsed.detail);
    } catch {
      /* fall through */
    }
  }
  return msg.replace(/^\d+\s+[\w\s]+:\s*/, "");
}
