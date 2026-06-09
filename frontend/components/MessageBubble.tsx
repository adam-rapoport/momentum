"use client";
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

export function MessageBubble({ role, text }: Props) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-lg px-4 py-2.5 text-sm ${
          isUser ? "bg-neutral-900 text-white" : "bg-white border border-neutral-200"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{text}</div>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
              {text}
            </ReactMarkdown>
          </div>
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
