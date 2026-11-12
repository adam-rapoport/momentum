"use client";
import { useState } from "react";
import type { ModelEntry } from "@/lib/api";

// "$2 in · $10 out per 1M tokens" — or "Free", or null when the backend has
// no price for the model (show nothing rather than something wrong).
export function priceLabel(m: ModelEntry): string | null {
  if (m.input_per_mtok == null || m.output_per_mtok == null) return null;
  const input = Number(m.input_per_mtok);
  const output = Number(m.output_per_mtok);
  if (!Number.isFinite(input) || !Number.isFinite(output)) return null;
  if (input === 0 && output === 0) return "Free";
  return `$${money(input)} in · $${money(output)} out per 1M tokens`;
}

// Whole dollars stay whole ($2); cents show two places ($0.75); the
// sub-cent rates some open models carry keep a third ($0.007) so they don't
// round to a misleading $0.01 or $0.00.
function money(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return n < 0.01 ? n.toFixed(3) : n.toFixed(2);
}

// Display names carry a provider suffix — "Claude Haiku 5.5 (Anthropic)" —
// that is noise wherever the provider is already on screen.
export function shortModelName(displayName: string): string {
  return displayName.replace(/\s*\([^)]*\)\s*$/, "");
}

// The model dropdown used by Settings → Models and the first-run wizard.
//
// One provider can offer dozens of models (OpenRouter has ~40), so the list
// is grouped rather than flat:
//   Recommended  — the short list the backend flags (`recommended`)
//   More models  — everything else that is current
//   Older models — anything with a newer replacement (`superseded_by`),
//                  hidden until asked for. Nothing is removed: the switch
//                  brings them all back, and the model you are already using
//                  always stays visible even when it is an older one.
// Under the dropdown: the selected model's one-line description and price.
export function ModelSelect({
  models,
  value,
  onChange,
  disabled,
  className = "",
}: {
  models: ModelEntry[];
  value: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [showOlder, setShowOlder] = useState(false);

  const current = models.filter((m) => !m.superseded_by);
  const recommended = current.filter((m) => m.recommended);
  const more = current.filter((m) => !m.recommended);
  const older = models.filter((m) => !!m.superseded_by);
  const olderShown = showOlder ? older : older.filter((m) => m.id === value);

  const selected = models.find((m) => m.id === value) ?? null;
  const price = selected ? priceLabel(selected) : null;

  const options = (list: ModelEntry[]) =>
    list.map((m) => (
      <option key={m.id} value={m.id}>
        {m.display_name}
      </option>
    ));

  // Group headings only earn their place when there is more than one group.
  const groups = [recommended, more, olderShown].filter((g) => g.length > 0).length;

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2.5">
        <label className="text-[12.5px] font-medium text-ink-muted">Model</label>
        <select
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="max-w-full rounded-[7px] border border-line-strong bg-surface px-2 py-1.5 text-[13px] text-ink"
        >
          {groups <= 1 ? (
            options([...recommended, ...more, ...olderShown])
          ) : (
            <>
              {recommended.length > 0 && <optgroup label="Recommended">{options(recommended)}</optgroup>}
              {more.length > 0 && <optgroup label="More models">{options(more)}</optgroup>}
              {olderShown.length > 0 && <optgroup label="Older models">{options(olderShown)}</optgroup>}
            </>
          )}
        </select>
        {older.length > 0 && (
          <button
            type="button"
            onClick={() => setShowOlder((x) => !x)}
            className="text-[12px] text-ink-dim underline decoration-dotted underline-offset-2 hover:text-ink"
          >
            {showOlder ? "Hide older models" : `Show older models (${older.length})`}
          </button>
        )}
      </div>
      {selected && (selected.notes || price) && (
        <div className="mt-2 max-w-[62ch]">
          {selected.notes && (
            <div className="text-[12px] leading-snug text-ink-muted">{selected.notes}</div>
          )}
          {price && <div className="mt-1 font-mono text-[11px] text-ink-dim">{price}</div>}
        </div>
      )}
    </div>
  );
}
