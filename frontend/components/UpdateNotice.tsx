"use client";
import { IconBtn, PixelIcon } from "@/components/pm";
import { useUiStore } from "@/lib/uiStore";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "";

// One-shot floating pill shown on the first launch after an app update.
// Fresh installs never see it — see restorePersisted in lib/uiStore.ts.
export function UpdateNotice() {
  const show = useUiStore((s) => s.updateNotice);
  const openSettings = useUiStore((s) => s.openSettings);
  const dismiss = useUiStore((s) => s.dismissUpdateNotice);
  if (!show) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-[10px] border border-line bg-surface py-1.5 pl-3 pr-1.5 shadow-pop">
      <PixelIcon name="sparkle" size={12} />
      <span className="text-[12.5px] text-ink">Updated to v{APP_VERSION}</span>
      <button
        type="button"
        onClick={() => openSettings("whatsnew")}
        className="rounded-[7px] border border-line bg-raised px-2 py-1 text-[11.5px] font-medium text-accent-text transition-colors duration-100 hover:border-accent"
      >
        See what&apos;s new
      </button>
      <IconBtn icon="x" size={10} title="Dismiss" onClick={dismiss} />
    </div>
  );
}
