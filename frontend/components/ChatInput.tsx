"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Kbd, PixelIcon, PxLabel } from "@/components/pm";
import { api, type CommandSummary } from "@/lib/api";

interface Props {
  onSend: (content: string) => void;
  onCancel: () => void;
  isStreaming: boolean;
  // Home-screen variant: larger type, autofocus, and external seeding from
  // the skill shortcut cards (seeds the draft, does NOT send).
  big?: boolean;
  autoFocus?: boolean;
  seed?: { text: string; nonce: number } | null;
}

// Matches a message that is still just a command token being typed at the very
// start — "/", "/wr", "/write-prd" — but NOT once a space follows ("/deep ho").
const COMMAND_TOKEN_RE = /^\/[a-z0-9-]*$/i;

export function ChatInput({ onSend, onCancel, isStreaming, big, autoFocus, seed }: Props) {
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
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [value]);

  // Seed from the home screen's skill shortcut cards.
  useEffect(() => {
    if (!seed || !seed.text) return;
    setValue(seed.text);
    setDismissed(true); // a space follows the command — keep the menu closed
    textareaRef.current?.focus();
  }, [seed]);

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
  const isCommand = value.startsWith("/");

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

  const canSend = Boolean(value.trim()) && !isStreaming;

  return (
    <div className="relative">
      {menuOpen ? (
        <div className="absolute bottom-full left-0 right-0 z-10 mb-2 overflow-hidden rounded-[12px] border border-line bg-surface shadow-pop">
          <div className="px-3.5 pb-1 pt-2.5">
            <PxLabel>Skills &amp; Commands</PxLabel>
          </div>
          <div className="max-h-72 overflow-y-auto pb-1.5">
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
                className={`flex w-full items-baseline gap-2.5 px-3.5 py-[7px] text-left ${
                  i === selectedIdx ? "bg-accent-tint" : ""
                }`}
              >
                <code
                  className={`font-mono text-[12.5px] font-semibold ${
                    i === selectedIdx ? "text-accent-text" : "text-ink"
                  }`}
                >
                  /{cmd.command}
                </code>
                <span className="min-w-0 truncate text-[12px] text-ink-muted">
                  {cmd.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div
        className={`rounded-[20px] border bg-surface shadow-composer transition-colors duration-150 ${
          isCommand ? "border-accent" : "border-line"
        }`}
      >
        <textarea
          ref={textareaRef}
          value={value}
          autoFocus={autoFocus}
          onChange={(e) => {
            setValue(e.target.value);
            setDismissed(false);
            setSelected(0);
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Message pMomentum — or type / for skills"
          className={`block w-full resize-none bg-transparent px-4 pt-3.5 outline-none placeholder:text-ink-dim focus-visible:shadow-none ${
            big ? "text-[15px]" : "text-[14px]"
          } ${isCommand ? "font-mono text-accent-text" : "text-ink"}`}
        />
        <div className="flex items-center gap-2 px-3 pb-2.5 pt-1.5">
          {isCommand ? (
            <span className="font-mono text-[11px] text-ink-dim">
              skill turn → routes to heavy model
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[11px] text-ink-dim">
              <Kbd>⏎</Kbd> send · <Kbd>⇧⏎</Kbd> newline
            </span>
          )}
          <span className="flex-1" />
          {isStreaming ? (
            <button
              type="button"
              onClick={onCancel}
              title="Stop responding"
              aria-label="Stop responding"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-app transition-transform hover:scale-105"
              style={{ color: "var(--bg-app)" }}
            >
              <PixelIcon name="stop" size={14} />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!canSend}
              title="Send"
              aria-label="Send"
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors ${
                canSend
                  ? "bg-accent text-accent-fg hover:brightness-105"
                  : "cursor-not-allowed bg-inset text-ink-dim"
              }`}
            >
              <PixelIcon name="arrowUp" size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
