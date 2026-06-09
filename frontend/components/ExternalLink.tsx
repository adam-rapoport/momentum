"use client";
import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { openExternal } from "@/lib/desktop";

/**
 * An anchor that actually works in the desktop app. The Tauri webview can't
 * navigate to external sites — a plain `<a target="_blank">` silently does
 * nothing — so we intercept the click and hand the URL to the OS browser via
 * the opener plugin (see lib/desktop.ts). In web dev it behaves like a normal
 * new-tab link.
 *
 * Also used directly as the `a` renderer for ReactMarkdown, hence the ignored
 * `node` prop (react-markdown passes it to custom components; spreading it
 * onto the DOM element would trigger a React warning).
 */
export function ExternalLink({
  node: _node,
  href,
  onClick,
  children,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & { node?: unknown }) {
  function handleClick(e: MouseEvent<HTMLAnchorElement>) {
    onClick?.(e);
    if (!href || e.defaultPrevented) return;
    e.preventDefault();
    void openExternal(href);
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
