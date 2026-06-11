"use client";
import { useEffect, useState } from "react";
import { Btn, Chip, PixelIcon, StatusDot } from "@/components/pm";
import { isTauri, openLocalPath, revealInFolder } from "@/lib/desktop";
import { useChatStore } from "@/lib/store";
import { ExternalLink } from "./ExternalLink";
import type {
  AwaitingReview,
  CreateEventPreview,
  PendingAction,
  SendEmailPreview,
} from "@/lib/types";

interface Props {
  review: AwaitingReview;
  onApprove: () => void;
  onRevise: (text: string) => void;
  onRestart: () => void;
}

// Approval card — replaces the composer while a deliverable/action is staged.
// Accent border + 5px dithered accent strip across the top (per the design).
export function ApprovalBar({ review, onApprove, onRevise, onRestart }: Props) {
  const [mode, setMode] = useState<"idle" | "revise">("idle");
  const [revision, setRevision] = useState("");

  function submitRevise() {
    const trimmed = revision.trim();
    if (!trimmed) return;
    onRevise(trimmed);
    setRevision("");
    setMode("idle");
  }

  const kind = review.kind ?? "deliverable";
  const headline = headlineForKind(kind);
  const approveLabel = approveLabelForKind(kind);

  return (
    <div className="overflow-hidden rounded-[14px] border border-accent bg-surface shadow-composer">
      <div className="dither h-[5px]" style={{ color: "var(--accent)" }} />
      <div className="p-3.5">
        <div className="mb-2.5 flex items-center gap-2">
          <StatusDot tone="accent" size={6} pulse />
          <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold text-ink">
            {headline}
          </span>
          {review.deliverable_kind && (
            <Chip tone="accent" mono>
              {review.deliverable_kind.replace(/_/g, " ")}
            </Chip>
          )}
        </div>

        <div className="mb-3 text-[13px] text-ink">
          {kind === "deliverable" ? (
            <DeliverablePreview review={review} />
          ) : (
            <ActionPreview action={review.pending_action ?? null} kind={kind} />
          )}
        </div>

        {mode === "idle" ? (
          <div className="flex items-center gap-2">
            <Btn kind="primary" onClick={onApprove}>
              <PixelIcon name="check" size={12} />
              {approveLabel}
            </Btn>
            <Btn onClick={() => setMode("revise")}>Make changes</Btn>
            <Btn kind="ghost" onClick={onRestart}>
              {kind === "deliverable" ? "Start over" : "Cancel"}
            </Btn>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            <textarea
              value={revision}
              onChange={(e) => setRevision(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitRevise();
                }
                if (e.key === "Escape") {
                  setMode("idle");
                  setRevision("");
                }
              }}
              rows={2}
              autoFocus
              placeholder={revisionPlaceholder(kind)}
              className="flex-1 resize-none rounded-[8px] border border-accent bg-surface px-3 py-2 text-[13px] text-ink shadow-[0_0_0_3px_var(--accent-tint)] outline-none placeholder:text-ink-dim focus-visible:shadow-[0_0_0_3px_var(--accent-tint)]"
            />
            <Btn kind="primary" onClick={submitRevise} disabled={!revision.trim()}>
              Send revision
            </Btn>
            <Btn
              kind="ghost"
              onClick={() => {
                setMode("idle");
                setRevision("");
              }}
            >
              Back
            </Btn>
          </div>
        )}
      </div>
    </div>
  );
}

function DeliverablePreview({ review }: { review: AwaitingReview }) {
  // For local deliverables (no Google Docs URL), find the file on disk via the
  // documents list — it refreshes on stream.done, i.e. just before this card
  // appears. Desktop-only affordance: a browser can't open local files.
  const documents = useChatStore((s) => s.documents);
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    setDesktop(isTauri());
  }, []);
  const localPath =
    !review.url && review.document_id
      ? (documents.find((d) => d.document_id === review.document_id && d.backend === "local")
          ?.file_path ?? null)
      : null;

  return (
    <div>
      {review.summary_for_user && <div className="text-ink">{review.summary_for_user}</div>}
      {(review.url || review.document_id) && (
        <div className="mt-2 flex items-center gap-2.5 rounded-[8px] border border-line-faint bg-raised px-2.5 py-2">
          <span className="shrink-0 text-ink-muted">
            <PixelIcon name="doc" size={13} />
          </span>
          <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-ink">
            {review.document_id ?? review.deliverable_kind}
          </span>
          {review.url && (
            <ExternalLink
              href={review.url}
              className="shrink-0 text-[12px] font-semibold text-accent-text hover:underline"
            >
              Open in Google Docs ↗
            </ExternalLink>
          )}
          {desktop && localPath && (
            <span className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                onClick={() => void openLocalPath(localPath)}
                className="rounded-[6px] border border-line bg-surface px-2 py-0.5 text-[12px] font-semibold text-accent-text hover:bg-raised"
                title="Open in your default app"
              >
                Open
              </button>
              <button
                type="button"
                onClick={() => void revealInFolder(localPath)}
                className="flex h-[22px] w-[22px] items-center justify-center rounded-[6px] border border-line bg-surface text-ink-muted hover:bg-raised hover:text-ink"
                title="Show in Finder"
              >
                <PixelIcon name="folder" size={11} />
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ActionPreview({
  action,
  kind,
}: {
  action: PendingAction | null;
  kind: AwaitingReview["kind"];
}) {
  if (!action) {
    return <div>Action staged for approval.</div>;
  }
  if (kind === "send_email") {
    return <EmailPreview preview={action.preview as SendEmailPreview} />;
  }
  if (kind === "create_event") {
    return <EventPreview preview={action.preview as CreateEventPreview} />;
  }
  return null;
}

function EmailPreview({ preview }: { preview: SendEmailPreview }) {
  return (
    <div className="rounded-[8px] border border-line-faint bg-raised p-3">
      <Field label="To" value={preview.to.join(", ")} mono />
      {preview.cc.length > 0 && <Field label="Cc" value={preview.cc.join(", ")} mono />}
      <Field label="Subject" value={preview.subject} bold />
      <div className="mt-2 whitespace-pre-wrap break-words border-t border-line-faint pt-2 text-[12.5px] text-ink-muted">
        {preview.body_snippet || "(empty body)"}
      </div>
    </div>
  );
}

function EventPreview({ preview }: { preview: CreateEventPreview }) {
  return (
    <div className="rounded-[8px] border border-line-faint bg-raised p-3">
      <Field label="Event" value={preview.summary} bold />
      <Field label="When" value={`${formatTime(preview.start_iso)} → ${formatTime(preview.end_iso)}`} />
      <Field label="Invitees" value={preview.attendees.join(", ") || "(none)"} mono />
      {preview.location && <Field label="Where" value={preview.location} />}
      {preview.description && (
        <div className="mt-2 whitespace-pre-wrap break-words border-t border-line-faint pt-2 text-[12.5px] text-ink-muted">
          {preview.description}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  bold,
  mono,
}: {
  label: string;
  value: string;
  bold?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex gap-2 py-px text-[12.5px]">
      <span className="w-14 shrink-0 text-ink-dim">{label}</span>
      <span
        className={`min-w-0 flex-1 break-words ${mono ? "font-mono text-[12px]" : ""} ${
          bold ? "font-semibold text-ink" : "text-ink"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function headlineForKind(kind: AwaitingReview["kind"]): string {
  if (kind === "send_email") return "Approve to send this email";
  if (kind === "create_event") return "Approve to send these calendar invites";
  return "Ready for your review";
}

function approveLabelForKind(kind: AwaitingReview["kind"]): string {
  if (kind === "send_email") return "Send email";
  if (kind === "create_event") return "Send invites";
  return "Looks good";
}

function revisionPlaceholder(kind: AwaitingReview["kind"]): string {
  if (kind === "send_email")
    return "What should change? e.g. 'make the tone friendlier' or 'add Carol to cc'";
  if (kind === "create_event")
    return "What should change? e.g. 'move to 3pm' or 'remove Carol'";
  return "What should change? e.g. 'add a non-goals section' or 'make the tone more casual'";
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
