"use client";
import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { openExternal } from "@/lib/desktop";

/**
 * An anchor that actually works in the desktop app. Two Tauri-webview traps
 * are handled here (both found the hard way, 2026-07-04):
 *
 * 1. The webview can't navigate to external sites, so we hand the URL to the
 *    OS browser (via the backend's /system/open-url — see lib/desktop.ts).
 * 2. Tauri injects a global click listener that calls preventDefault() on
 *    every `target="_blank"` anchor click BEFORE React handlers run — its way
 *    of blocking popup windows. A naive "respect e.defaultPrevented" check
 *    therefore silently drops every real click in the desktop app (while
 *    working fine in a browser and in synthetic-event tests). So we only
 *    honor a cancellation made by OUR caller's onClick, not one that arrived
 *    pre-set on the event.
 *
 * Also used as the `a` renderer for ReactMarkdown, hence the ignored `node`
 * prop (react-markdown passes it; spreading it onto the DOM would warn).
 */
export function ExternalLink({
  node: _node,
  href,
  onClick,
  children,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & { node?: unknown }) {
  function handleClick(e: MouseEvent<HTMLAnchorElement>) {
    const cancelledBeforeUs = e.defaultPrevented; // Tauri's _blank interceptor
    onClick?.(e);
    if (!href) return;
    if (!cancelledBeforeUs && e.defaultPrevented) return; // caller's veto
    e.preventDefault();
    openExternal(href).catch((err) => {
      console.error(`[ExternalLink] failed to open ${href}:`, err);
      window.open(href, "_blank", "noopener,noreferrer");
    });
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      {...rest}
      onClick={handleClick}
    >
      {children}
    </a>
  );
}
