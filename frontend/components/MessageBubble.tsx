"use client";
import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { PmLogo } from "@/components/pm";
import { ExternalLink } from "./ExternalLink";

// Markdown links (e.g. web-search citations, Google Docs URLs the model
// includes) must open via the OS browser in the desktop webview.
const MD_COMPONENTS: Components = { a: ExternalLink };

interface Props {
  role: "user" | "assistant";
  text: string;
}

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard API can be unavailable in the webview — fall back to the
    // legacy selection trick.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      title="Copy message"
      aria-label="Copy message"
      onClick={() => {
        void copyText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="mt-1 hidden rounded-[5px] border border-line bg-surface px-1.5 py-0.5 font-mono text-[10px] text-ink-dim hover:text-ink group-hover:inline-block"
    >
      {copied ? "Copied ✓" : "Copy"}
    </button>
  );
}

// 26px logo avatar chip used by assistant messages and the thinking row.
export function AssistantAvatar({ pulse }: { pulse?: boolean }) {
  return (
    <span
      className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[8px] border border-line bg-surface ${
        pulse ? "pm-pulse" : ""
      }`}
    >
      <PmLogo size={13} />
    </span>
  );
}

export function MessageBubble({ role, text }: Props) {
  if (role === "user") {
    return (
      <div className="pm-enter flex justify-end">
        <div className="max-w-[78%] whitespace-pre-wrap rounded-[14px_14px_4px_14px] border border-line bg-surface px-3.5 py-2.5 text-[14px] text-ink shadow-card">
          {text}
        </div>
      </div>
    );
  }
  return (
    <div className="pm-enter group flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="markdown-body text-[14.5px] text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {text}
          </ReactMarkdown>
        </div>
        <CopyButton text={text} />
      </div>
    </div>
  );
}

export function StreamingBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="markdown-body text-[14.5px] text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {text}
          </ReactMarkdown>
          <span className="pm-cursor" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
