"use client";
import { useEffect, useRef, useState } from "react";

interface Props {
  onSend: (content: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onCancel, isStreaming, disabled }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-neutral-200 bg-white p-3">
      <div className="flex items-end gap-2 max-w-3xl mx-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={disabled ? "…" : "Message pMomentum (Enter to send, Shift+Enter for newline)"}
          disabled={disabled}
          className="flex-1 resize-none rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-400 disabled:bg-neutral-100"
        />
        {isStreaming ? (
          <button
            onClick={onCancel}
            className="rounded-md bg-neutral-200 text-neutral-800 text-sm font-medium px-4 py-2 hover:bg-neutral-300"
          >
            Cancel
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim() || disabled}
            className="rounded-md bg-neutral-900 text-white text-sm font-medium px-4 py-2 hover:bg-neutral-800 disabled:bg-neutral-400 disabled:cursor-not-allowed"
          >
            Send
          </button>
        )}
      </div>
      <div className="max-w-3xl mx-auto mt-1.5 px-0.5 text-[11px] text-neutral-400">
        Tip: start a message with <code className="text-neutral-500">/deep</code> to use the more capable model for one reply.
      </div>
    </div>
  );
}
