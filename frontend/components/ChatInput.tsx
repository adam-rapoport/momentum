"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Kbd, PixelIcon, PxLabel } from "@/components/pm";
import { api, type CommandSummary } from "@/lib/api";
import { errorMessage } from "@/lib/errors";

interface ChatAttachment {
  id: string;
  filename: string;
}

interface Props {
  onSend: (content: string, attachments: ChatAttachment[]) => void;
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
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploadCount, setUploadCount] = useState(0);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function addFiles(files: FileList | File[] | null | undefined) {
    const list = files ? Array.from(files) : [];
    if (list.length === 0) return;
    setAttachError(null);
    setUploadCount((n) => n + list.length);
    for (const file of list) {
      try {
        const r = await api.uploadChatAttachment(file);
        setAttachments((prev) => [...prev, { id: r.attachment_id, filename: r.filename }]);
      } catch (e) {
        setAttachError(errorMessage(e));
      } finally {
        setUploadCount((n) => n - 1);
      }
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  function removeAttachment(id: string) {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }

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
    const uploading = uploadCount > 0;
    if ((!trimmed && attachments.length === 0) || isStreaming || uploading) return;
    onSend(trimmed, attachments);
    setValue("");
    setAttachments([]);
    setAttachError(null);
    setDismissed(false);
  }

  const uploading = uploadCount > 0;
  const canSend =
    (Boolean(value.trim()) || attachments.length > 0) && !isStreaming && !uploading;

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

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.pptx,.xlsx,.csv,.tsv,.md,.markdown,.txt"
        multiple
        className="hidden"
        onChange={(e) => void addFiles(e.target.files)}
      />

      <div
        className={`rounded-[20px] border bg-surface shadow-composer transition-colors duration-150 ${
          dragOver
            ? "border-accent ring-2 ring-accent"
            : isCommand
              ? "border-accent"
              : "border-line"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!isStreaming) setDragOver(true);
        }}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void addFiles(e.dataTransfer.files);
        }}
      >
        {(attachments.length > 0 || uploading) && (
          <div className="flex flex-wrap gap-1.5 px-3 pt-3">
            {attachments.map((a) => (
              <span
                key={a.id}
                className="inline-flex items-center gap-1.5 rounded-[7px] border border-line bg-raised px-2 py-1 text-[11.5px] text-ink"
              >
                <PixelIcon name="doc" size={10} />
                <span className="max-w-[160px] truncate">{a.filename}</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(a.id)}
                  title="Remove attachment"
                  aria-label={`Remove ${a.filename}`}
                  className="text-ink-dim hover:text-ink"
                >
                  <PixelIcon name="x" size={9} />
                </button>
              </span>
            ))}
            {uploading && (
              <span className="inline-flex items-center rounded-[7px] border border-line bg-raised px-2 py-1 text-[11.5px] text-ink-dim">
                Analyzing…
              </span>
            )}
          </div>
        )}
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
          placeholder="Message Momentum — or type / for skills"
          className={`block w-full resize-none bg-transparent px-4 pt-3.5 outline-none placeholder:text-ink-dim focus-visible:shadow-none ${
            big ? "text-[15px]" : "text-[14px]"
          } ${isCommand ? "font-mono text-accent-text" : "text-ink"}`}
        />
        <div className="flex items-center gap-2 px-3 pb-2.5 pt-1.5">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            title="Attach a document (PDF, Word, PowerPoint, Excel, CSV, Markdown, text)"
            aria-label="Attach a document"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-dim transition-colors hover:bg-inset hover:text-ink"
          >
            <PixelIcon name="plus" size={13} />
          </button>
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
      {attachError && (
        <div className="mt-1.5 px-3 text-[11.5px] text-danger">{attachError}</div>
      )}
    </div>
  );
}
