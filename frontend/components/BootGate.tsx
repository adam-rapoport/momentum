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
const MAX_ATTEMPTS = 120; // ~60s before giving up

type Phase = "loading" | "ready" | "error";

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
        if (attempts >= MAX_ATTEMPTS) {
          setPhase("error");
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
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

      {phase === "error" ? (
        <>
          <div style={{ color: "var(--text-muted)" }} className="text-sm">
            Couldn&apos;t reach the backend. It may still be starting up.
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
        <>
          <div
            className="h-6 w-6 animate-spin rounded-full border-2 border-transparent"
            style={{ borderTopColor: "var(--accent)", borderRightColor: "var(--accent)" }}
            aria-hidden
          />
          <div style={{ color: "var(--text-muted)" }} className="text-sm">
            Starting pMomentum…
          </div>
        </>
      )}
    </div>
  );
}
