"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

// Settings now lives in a modal sheet over the chat. This stub only exists so
// old links — and the Google OAuth callback's redirect — still land somewhere
// sensible, preserving the ?google=connected|error flag.
function SettingsRedirect() {
  const router = useRouter();
  const search = useSearchParams();

  useEffect(() => {
    const params = new URLSearchParams();
    const google = search.get("google");
    const reason = search.get("reason");
    params.set("settings", google ? "integrations" : "models");
    if (google) params.set("google", google);
    if (reason) params.set("reason", reason);
    router.replace(`/chat?${params.toString()}`);
  }, [router, search]);

  return null;
}

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsRedirect />
    </Suspense>
  );
}
