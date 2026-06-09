"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

// Gates the whole app behind a backend-readiness check, and shows a loading
// screen while we wait. The desktop window appears immediately (so the user
// sees this instead of a blank wait), but the bundled Python backend takes a
// few seconds to boot (PyInstaller unpack + DB migrations + seeding). Until
// it's serving, every "on mount" data fetch (sessions, memories, profile)
// would fail silently — so we don't render the app until the backend answers.
//
// The same readiness probe doubles as the onboarding decision: `/onboarding/
// status` only responds once the backend lifespan has finished seeding the
// default user, so a successful call means the DB is ready. We route first-run
// users to the wizard based on `completed_at` (did they finish onboarding),
// not `configured` (do they merely have a key) — so onboarding is reliable
// even when a key is already present.

const POLL_INTERVAL_MS = 500;
const STALLED_AFTER_ATTEMPTS = 40; // ~20s: switch to the "taking longer" copy
const STALLED_POLL_INTERVAL_MS = 2000;

// "stalled" means the backend still hasn't answered after a while. We never
// stop polling (a slow first-run PyInstaller unpack + migration can blow any
// fixed ceiling) — the copy just changes and a manual "Try again" resets the
// fast poll cadence.
type Phase = "loading" | "ready" | "stalled";

export function BootGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [phase, setPhase] = useState<Phase>("loading");
  const [restartKey, setRestartKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;

    async function poll() {
      try {
        const status = await api.onboardingStatus();
        if (cancelled) return;
        // Backend is up. Send first-run users to onboarding; keep the loading
        // screen up during the redirect so the chat UI never flashes.
        if (!status.completed_at && !pathname?.startsWith("/onboarding")) {
          router.replace("/onboarding");
          return;
        }
        setPhase("ready");
      } catch {
        if (cancelled) return;
        attempts += 1;
        if (attempts >= STALLED_AFTER_ATTEMPTS) {
          setPhase("stalled");
          timer = setTimeout(poll, STALLED_POLL_INTERVAL_MS);
        } else {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    }

    setPhase("loading");
    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [pathname, router, restartKey]);

  if (phase === "ready") return <>{children}</>;

  return (
    <BootScreen
      phase={phase}
      onRetry={() => setRestartKey((k) => k + 1)}
    />
  );
}

function BootScreen({ phase, onRetry }: { phase: Phase; onRetry: () => void }) {
  return (
    <div
      className="flex h-screen w-screen flex-col items-center justify-center gap-4"
      style={{ background: "var(--bg-canvas)", color: "var(--text)" }}
    >
      <div className="text-lg font-semibold tracking-tight">pMomentum</div>

      <div
        className="h-6 w-6 animate-spin rounded-full border-2 border-transparent"
        style={{ borderTopColor: "var(--accent)", borderRightColor: "var(--accent)" }}
        aria-hidden
      />
      {phase === "stalled" ? (
        <>
          <div style={{ color: "var(--text-muted)" }} className="text-sm text-center max-w-sm">
            Still starting… this is taking longer than usual. We&apos;ll keep
            trying — or restart the app if it never comes up.
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md px-4 py-2 text-sm font-medium"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            Try again
          </button>
        </>
      ) : (
        <div style={{ color: "var(--text-muted)" }} className="text-sm">
          Starting pMomentum…
        </div>
      )}
    </div>
  );
}
