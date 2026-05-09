"use client";
import { useState } from "react";
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
    <div className="border-t border-indigo-200 bg-indigo-50/60 p-3">
      <div className="max-w-3xl mx-auto">
        <div className="mb-3 flex items-start gap-2">
          <span className="mt-0.5 inline-block w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
          <div className="text-sm text-indigo-900 flex-1 min-w-0">
            <div className="font-medium">{headline}</div>
            {kind === "deliverable" ? (
              <DeliverablePreview review={review} />
            ) : (
              <ActionPreview action={review.pending_action ?? null} kind={kind} />
            )}
          </div>
        </div>

        {mode === "idle" ? (
          <div className="flex items-center gap-2">
            <button
              onClick={onApprove}
              className="rounded-md bg-indigo-600 text-white text-sm font-medium px-4 py-2 hover:bg-indigo-700"
            >
              {approveLabel}
            </button>
            <button
              onClick={() => setMode("revise")}
              className="rounded-md bg-white ring-1 ring-inset ring-indigo-300 text-indigo-700 text-sm font-medium px-4 py-2 hover:bg-indigo-100"
            >
              Make changes
            </button>
            <button
              onClick={onRestart}
              className="rounded-md bg-white ring-1 ring-inset ring-neutral-300 text-neutral-700 text-sm font-medium px-4 py-2 hover:bg-neutral-100"
            >
              {kind === "deliverable" ? "Start over" : "Cancel"}
            </button>
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
              className="flex-1 resize-none rounded-md border border-indigo-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={submitRevise}
              disabled={!revision.trim()}
              className="rounded-md bg-indigo-600 text-white text-sm font-medium px-4 py-2 hover:bg-indigo-700 disabled:bg-neutral-400 disabled:cursor-not-allowed"
            >
              Send revision
            </button>
            <button
              onClick={() => {
                setMode("idle");
                setRevision("");
              }}
              className="rounded-md bg-white ring-1 ring-inset ring-neutral-300 text-neutral-700 text-sm font-medium px-4 py-2 hover:bg-neutral-100"
            >
              Back
            </button>
          </div>
        )}
      </div>
    </div>
  );
}


function DeliverablePreview({ review }: { review: AwaitingReview }) {
  return (
    <div>
      {review.deliverable_kind && (
        <div className="text-indigo-700 text-xs uppercase tracking-wide mb-1">
          {review.deliverable_kind.replace(/_/g, " ")}
        </div>
      )}
      {review.summary_for_user && (
        <div className="text-indigo-800">{review.summary_for_user}</div>
      )}
      {review.document_id && (
        <div className="mt-0.5 text-xs text-indigo-700">
          Document: <span className="font-mono">{review.document_id}</span>
        </div>
      )}
      {review.url && (
        <div className="mt-2">
          <a
            href={review.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md bg-white ring-1 ring-inset ring-indigo-300 text-indigo-700 text-sm font-medium px-3 py-1.5 hover:bg-indigo-100"
          >
            Open in Google Docs
            <span aria-hidden="true">↗</span>
          </a>
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
    return <div className="text-indigo-800">Action staged for approval.</div>;
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
    <div className="rounded-md bg-white ring-1 ring-inset ring-indigo-200 p-3 mt-1">
      <Field label="To" value={preview.to.join(", ")} />
      {preview.cc.length > 0 && (
        <Field label="Cc" value={preview.cc.join(", ")} />
      )}
      <Field label="Subject" value={preview.subject} bold />
      <div className="mt-2 text-sm text-neutral-800 whitespace-pre-wrap break-words">
        {preview.body_snippet || "(empty body)"}
      </div>
    </div>
  );
}

function EventPreview({ preview }: { preview: CreateEventPreview }) {
  return (
    <div className="rounded-md bg-white ring-1 ring-inset ring-indigo-200 p-3 mt-1">
      <Field label="Event" value={preview.summary} bold />
      <Field
        label="When"
        value={`${formatTime(preview.start_iso)} → ${formatTime(preview.end_iso)}`}
      />
      <Field label="Attendees" value={preview.attendees.join(", ") || "(none)"} />
      {preview.location && <Field label="Where" value={preview.location} />}
      {preview.description && (
        <div className="mt-2 text-sm text-neutral-700 whitespace-pre-wrap break-words">
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
}: {
  label: string;
  value: string;
  bold?: boolean;
}) {
  return (
    <div className="text-sm flex gap-2">
      <span className="text-neutral-500 w-20 shrink-0">{label}</span>
      <span
        className={`flex-1 min-w-0 break-words ${bold ? "font-medium text-neutral-900" : "text-neutral-800"}`}
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
