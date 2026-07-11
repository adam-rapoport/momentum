"use client";
import { Kbd, PxLabel } from "@/components/pm";

// Plain-English "how to use" guide. Pure content, no state — sections are
// data-driven so copy edits don't touch markup.
const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: "What is Momentum?",
    body: (
      <>
        Momentum is an AI assistant for product management work that runs entirely on your Mac.
        It chats, drafts documents, remembers what matters, and connects to your tools — and your
        conversations never pass through a Momentum server. You bring your own AI provider key
        (or run a local model), and the app talks to that provider directly.
      </>
    ),
  },
  {
    title: "Chat basics",
    body: (
      <>
        Type in the composer and press Enter. The agent can use tools mid-answer — searching the
        web, reading your memory, checking your calendar — and you&apos;ll see each step appear as
        a card in the conversation. Use the stop button to cancel a response that&apos;s going the
        wrong way.
      </>
    ),
  },
  {
    title: "Skills & slash commands",
    body: (
      <>
        Type <Kbd>/</Kbd> in the composer to see every skill — ready-made workflows like{" "}
        <code className="font-mono text-[12px]">/write-prd</code>,{" "}
        <code className="font-mono text-[12px]">/stakeholder-update</code>, and{" "}
        <code className="font-mono text-[12px]">/meeting-prep</code>. A skill walks a structured
        process and ends with a real deliverable. Skill turns automatically route to your{" "}
        <em>heavy</em> model (the stronger one you picked for big drafting jobs). Tip: prefix any
        ordinary message with <code className="font-mono text-[12px]">/deep</code> to force that
        one message onto the heavy model.
      </>
    ),
  },
  {
    title: "Memory",
    body: (
      <>
        When you tell the agent something durable — a stakeholder&apos;s preferences, a decision
        and its rationale, how your team works — it saves a memory and uses it in every future
        conversation. Open the Memory panel (right side) to browse everything it knows. You can
        also click &quot;Add from document&quot; there to upload a PDF, Word doc, PowerPoint,
        Excel or CSV file, markdown, or text: the agent reads it and turns the durable
        facts into memories.
      </>
    ),
  },
  {
    title: "Documents",
    body: (
      <>
        When a skill produces a deliverable — a PRD, an update, release notes — it lands in the
        Documents panel. If you&apos;ve connected Google in Settings → Integrations, deliverables
        can be created as Google Docs you can share; otherwise they&apos;re saved as files on this
        Mac.
      </>
    ),
  },
  {
    title: "Approvals",
    body: (
      <>
        Before anything leaves your machine — sending an email, creating a calendar event,
        finalizing a deliverable — Momentum pauses and shows you exactly what it wants to do.
        Approve it, ask for a revision, or restart. Nothing is sent without your say-so.
      </>
    ),
  },
  {
    title: "Models: light vs heavy",
    body: (
      <>
        Momentum routes each message to one of two model slots you configure in Settings →
        Models. The <em>light</em> model handles everyday turns — fast and cheap. The{" "}
        <em>heavy</em> model handles big asks: drafting, synthesis, long reasoning. Skills always
        use the heavy slot. You can mix providers freely — for example a free Groq model for
        light work and Gemini, Claude, or a local Ollama model for heavy work.
      </>
    ),
  },
];

export function HelpPane() {
  return (
    <div>
      <div className="mb-4">
        <PxLabel>How to use</PxLabel>
      </div>
      <div className="flex flex-col gap-3">
        {SECTIONS.map((s) => (
          <section
            key={s.title}
            className="rounded-[12px] border border-line bg-surface p-4 shadow-card"
          >
            <h3 className="mb-1.5 text-[13px] font-semibold text-ink">{s.title}</h3>
            <p className="text-[12.5px] leading-relaxed text-ink-muted">{s.body}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
