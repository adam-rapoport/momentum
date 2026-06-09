"use client";
import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
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
      className="absolute -bottom-2.5 right-2 hidden group-hover:block rounded border border-neutral-200 bg-white px-1.5 py-0.5 text-[10px] text-neutral-500 shadow-sm hover:text-neutral-900"
    >
      {copied ? "Copied ✓" : "Copy"}
    </button>
  );
}

export function MessageBubble({ role, text }: Props) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`group relative max-w-2xl rounded-lg px-4 py-2.5 text-sm ${
          isUser ? "bg-neutral-900 text-white" : "bg-white border border-neutral-200"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{text}</div>
        ) : (
          <>
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                {text}
              </ReactMarkdown>
            </div>
            <CopyButton text={text} />
          </>
        )}
      </div>
    </div>
  );
}

export function StreamingBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl rounded-lg px-4 py-2.5 text-sm bg-white border border-neutral-200">
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {text}
          </ReactMarkdown>
          <span className="inline-block w-2 h-4 bg-neutral-400 ml-0.5 animate-pulse align-middle" />
        </div>
      </div>
    </div>
  );
}
