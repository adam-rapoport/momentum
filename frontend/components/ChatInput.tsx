"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CommandSummary } from "@/lib/api";

interface Props {
  onSend: (content: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
}

// Matches a message that is still just a command token being typed at the very
// start — "/", "/wr", "/write-prd" — but NOT once a space follows ("/deep ho").
const COMMAND_TOKEN_RE = /^\/[a-z0-9-]*$/i;

export function ChatInput({ onSend, onCancel, isStreaming }: Props) {
  const [value, setValue] = useState("");
  const [commands, setCommands] = useState<CommandSummary[]>([]);
  const [selected, setSelected] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load the available slash commands once. The backend is already up by the
  // time the chat renders (BootGate), so this normally succeeds; on failure we
  // just don't show the menu.
  useEffect(() => {
    api
      .listCommands()
      .then((res) => setCommands(res.commands))
      .catch(() => setCommands([]));
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  // The "/" menu is shown while the user is typing a command token at the start
  // of an otherwise-empty message, and hasn't dismissed it with Escape.
  const matches = useMemo(() => {
    if (dismissed || isStreaming) return [];
    if (!COMMAND_TOKEN_RE.test(value)) return [];
    const q = value.slice(1).toLowerCase();
    return commands.filter((c) => c.command.toLowerCase().startsWith(q));
  }, [value, commands, dismissed, isStreaming]);

  const menuOpen = matches.length > 0;
  const selectedIdx = Math.min(selected, matches.length - 1);

  function chooseCommand(cmd: CommandSummary) {
    setValue(`/${cmd.command} `);
    setDismissed(true); // hide the menu now that a space follows
    setSelected(0);
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (menuOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelected((i) => (i + 1) % matches.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelected((i) => (i - 1 + matches.length) % matches.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        chooseCommand(matches[selectedIdx]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setDismissed(true);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    setDismissed(false);
  }

  return (
    <div className="border-t border-neutral-200 bg-white p-3">
      <div className="relative max-w-3xl mx-auto">
        {menuOpen ? (
          <div className="absolute bottom-full mb-2 left-0 right-0 z-10 max-h-72 overflow-y-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
            {matches.map((cmd, i) => (
              <button
                key={cmd.command}
                // onMouseDown (not onClick) so the textarea doesn't blur first
                // and swallow the selection.
                onMouseDown={(e) => {
                  e.preventDefault();
                  chooseCommand(cmd);
                }}
                onMouseEnter={() => setSelected(i)}
                ref={(el) => {
                  if (i === selectedIdx) el?.scrollIntoView({ block: "nearest" });
                }}
                className={`flex w-full items-baseline gap-2 px-3 py-2 text-left ${
                  i === selectedIdx ? "bg-neutral-100" : "bg-white"
                }`}
              >
                <code className="text-sm font-medium text-neutral-900">/{cmd.command}</code>
                <span className="truncate text-xs text-neutral-500">{cmd.description}</span>
              </button>
            ))}
          </div>
        ) : null}
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setDismissed(false);
              setSelected(0);
            }}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Message pMomentum (Enter to send, Shift+Enter for newline)"
            className="flex-1 resize-none rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-400"
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
              disabled={!value.trim()}
              className="rounded-md bg-neutral-900 text-white text-sm font-medium px-4 py-2 hover:bg-neutral-800 disabled:bg-neutral-400 disabled:cursor-not-allowed"
            >
              Send
            </button>
          )}
        </div>
      </div>
      <div className="max-w-3xl mx-auto mt-1.5 px-0.5 text-[11px] text-neutral-400">
        Tip: type <code className="text-neutral-500">/</code> to see commands and skills.
      </div>
    </div>
  );
}
