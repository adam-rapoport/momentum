"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

// Redirects to /onboarding when the app isn't configured yet (no usable LLM
// key). Renders nothing itself — drop it inside a layout. Single-user app, so
// a client-side check is sufficient.
export function OnboardingGate() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname?.startsWith("/onboarding")) return;
    let cancelled = false;
    api
      .onboardingStatus()
      .then((s) => {
        if (!cancelled && !s.configured) router.replace("/onboarding");
      })
      .catch(() => {
        /* if status can't be read, leave the user where they are */
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return null;
}
