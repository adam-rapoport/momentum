"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

function OnboardingInner() {
  const router = useRouter();
  const search = useSearchParams();
  const restart = search.get("restart") === "1";
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .onboardingStatus()
      .then((s) => {
        if (cancelled) return;
        // Reverse-guard: onboarding already finished and not an explicit re-run.
        // Keyed on `completed_at` (did the wizard finish), matching BootGate —
        // gating on `configured` instead would ping-pong with it whenever a key
        // exists but onboarding was never completed.
        if (s.completed_at && !restart) {
          router.replace("/chat");
        } else {
          setReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) setReady(true); // show wizard if status can't be read
      });
    return () => {
      cancelled = true;
    };
  }, [restart, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-app font-mono text-[12px] text-ink-dim">
        Loading…
      </div>
    );
  }

  return <OnboardingWizard />;
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <OnboardingInner />
    </Suspense>
  );
}
