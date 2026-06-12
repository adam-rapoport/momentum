"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChatInput } from "@/components/ChatInput";
import { Kbd, PixelIcon, PmLogo, type PixelIconName } from "@/components/pm";
import { api } from "@/lib/api";
import { useChatStore } from "@/lib/store";
import { useUiStore } from "@/lib/uiStore";

// The six skill shortcuts shown on the empty home state. Clicking one seeds
// the composer with the command (it does NOT send).
const SKILL_CARDS: { command: string; label: string; icon: PixelIconName }[] = [
  { command: "write-prd", label: "Write a PRD", icon: "doc" },
  { command: "stakeholder-update", label: "Stakeholder update", icon: "mail" },
  { command: "meeting-prep", label: "Meeting prep", icon: "calendar" },
  { command: "feedback-synthesis", label: "Synthesize feedback", icon: "sparkle" },
  { command: "release-notes", label: "Release notes", icon: "tag" },
  { command: "decision-log", label: "Decision log", icon: "check" },
];

function timeGreeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Good evening";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

// Derive a session title from the first message: command → skill name,
// otherwise the first ~34 characters.
function deriveTitle(text: string): string {
  if (text.startsWith("/")) {
    const name = text.split(" ")[0].slice(1).replace(/-/g, " ");
    return name.charAt(0).toUpperCase() + name.slice(1);
  }
  return text.length > 34 ? `${text.slice(0, 34)}…` : text;
}

export function HomeView() {
  const router = useRouter();
  const upsertSession = useChatStore((s) => s.upsertSession);
  const profile = useUiStore((s) => s.profile);
  const setQueuedFirstMessage = useUiStore((s) => s.setQueuedFirstMessage);
  const openSettings = useUiStore((s) => s.openSettings);

  const [seed, setSeed] = useState<{ text: string; nonce: number } | null>(null);
  const [skillCount, setSkillCount] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .listCommands()
      .then((res) => setSkillCount(res.commands.filter((c) => c.kind === "skill").length))
      .catch(() => setSkillCount(null));
  }, []);

  const firstName = profile?.display_name?.split(" ")[0];
  const greeting = firstName && firstName !== "You" ? `${timeGreeting()}, ${firstName}` : timeGreeting();

  // Create the session on first send (no more eager empty sessions), queue
  // the message, and let ChatView send it once its initial load resolves.
  async function handleSend(text: string) {
    if (creating) return;
    setCreating(true);
    try {
      const session = await api.createSession({ title: deriveTitle(text) });
      upsertSession(session);
      setQueuedFirstMessage({ sessionId: session.id, content: text });
      router.push(`/chat?s=${session.id}`);
    } catch (err) {
      console.error("failed to create session:", err);
      setCreating(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-[640px] flex-col justify-center px-6 py-10">
        <div className="mb-7 text-center">
          <div className="mb-4 flex justify-center">
            <PmLogo size={28} />
          </div>
          <h1 className="text-[27px] font-bold tracking-[-0.02em] text-ink">{greeting}</h1>
          <p className="mt-1.5 text-[13.5px] text-ink-muted">What are we moving forward today?</p>
        </div>

        <ChatInput
          onSend={handleSend}
          onCancel={() => undefined}
          isStreaming={creating}
          big
          autoFocus
          seed={seed}
        />

        <div className="mt-5 grid gap-2.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
          {SKILL_CARDS.map((card) => (
            <button
              key={card.command}
              type="button"
              onClick={() => setSeed({ text: `/${card.command} `, nonce: Date.now() })}
              className="flex items-center gap-2.5 rounded-[10px] border border-line bg-surface px-3 py-2.5 text-left shadow-card transition-colors duration-100 hover:border-accent"
            >
              <span className="shrink-0 text-accent">
                <PixelIcon name={card.icon} size={13} />
              </span>
              <span className="min-w-0 truncate text-[12.5px] font-[550] text-ink">{card.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-6 text-center text-[11.5px] text-ink-dim">
          Type <Kbd>/</Kbd> in the composer to see all{skillCount ? ` ${skillCount}` : ""} skills
          <div className="mt-2">
            <button
              type="button"
              onClick={() => openSettings("help")}
              className="text-[11.5px] text-ink-dim underline underline-offset-2 hover:text-ink-muted"
            >
              How pMomentum works
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
