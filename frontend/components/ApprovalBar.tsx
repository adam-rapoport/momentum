"use client";
import { useState } from "react";
import type { AwaitingReview } from "@/lib/types";

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

  return (
    <div className="border-t border-indigo-200 bg-indigo-50/60 p-3">
      <div className="max-w-3xl mx-auto">
        <div className="mb-2 flex items-start gap-2">
          <span className="mt-0.5 inline-block w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
          <div className="text-sm text-indigo-900">
            <div className="font-medium">
              Ready for your review
              {review.deliverable_kind && (
                <span className="font-normal text-indigo-700">
                  {" "}
                  · {review.deliverable_kind.replace(/_/g, " ")}
                </span>
              )}
            </div>
            {review.summary_for_user && (
              <div className="mt-0.5 text-indigo-800">{review.summary_for_user}</div>
            )}
            {review.document_id && (
              <div className="mt-0.5 text-xs text-indigo-700">
                Document:{" "}
                <span className="font-mono">{review.document_id}</span>
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
        </div>

        {mode === "idle" ? (
          <div className="flex items-center gap-2">
            <button
              onClick={onApprove}
              className="rounded-md bg-indigo-600 text-white text-sm font-medium px-4 py-2 hover:bg-indigo-700"
            >
              Looks good
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
              Start over
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
              placeholder="What should change? e.g. 'add a non-goals section' or 'make the tone more casual'"
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
