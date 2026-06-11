"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Btn, PmLogo } from "@/components/pm";
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
      data-tauri-drag-region=""
      className="flex h-screen w-screen flex-col items-center justify-center gap-4 bg-app text-ink"
    >
      <span className="pm-pulse">
        <PmLogo size={32} />
      </span>
      <div className="font-pixel text-[13px] tracking-[0.08em]">PMOMENTUM</div>
      {phase === "stalled" ? (
        <>
          <div className="max-w-sm text-center text-sm text-ink-muted">
            Still starting… this is taking longer than usual. We&apos;ll keep trying — or restart
            the app if it never comes up.
          </div>
          <Btn kind="primary" size="sm" onClick={onRetry}>
            Try again
          </Btn>
        </>
      ) : (
        <div className="font-mono text-[12px] text-ink-muted">Starting pMomentum…</div>
      )}
    </div>
  );
}
