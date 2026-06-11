"use client";
import { useEffect } from "react";
import { isTauri } from "@/lib/desktop";

// Marks <html data-desktop> after mount when running inside the Tauri shell.
// CSS keys off it for desktop-only chrome (the traffic-light inset). Applied
// post-mount so server-rendered HTML matches the first client render.
export function DesktopFlag() {
  useEffect(() => {
    if (isTauri()) document.documentElement.dataset.desktop = "true";
  }, []);
  return null;
}
