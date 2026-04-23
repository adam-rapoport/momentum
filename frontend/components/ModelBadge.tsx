"use client";

interface ModelBadgeProps {
  model?: string;
}

// Map full model IDs to short friendly names. Unknown models fall through
// to the last `/`-separated segment so the badge is still useful.
function shortName(model: string): string {
  if (model.includes("llama-4-scout")) return "Scout";
  if (model.startsWith("gemini-3.1-pro")) return "Gemini 3.1 Pro";
  if (model.startsWith("gemini-3-pro")) return "Gemini 3 Pro";
  if (model.startsWith("gemini-3-flash")) return "Gemini 3 Flash";
  if (model.startsWith("gemini-2.5-pro")) return "Gemini 2.5 Pro";
  if (model.startsWith("gemini-2.5-flash-lite")) return "Gemini 2.5 Flash-Lite";
  if (model.startsWith("gemini-2.5-flash")) return "Gemini 2.5 Flash";
  if (model.startsWith("gemma-4")) return "Gemma 4";
  if (model.startsWith("gemma-3")) return "Gemma 3";
  if (model.includes("gpt-oss-120b")) return "GPT-OSS 120B";
  if (model.includes("gpt-oss-20b")) return "GPT-OSS 20B";
  if (model.includes("qwen3")) return "Qwen 3";
  if (model.includes("llama-3.3")) return "Llama 3.3";
  const slash = model.lastIndexOf("/");
  return slash >= 0 ? model.slice(slash + 1) : model;
}

function isHeavy(model: string): boolean {
  // Any model that isn't the default Scout is styled as "heavy".
  return !model.includes("llama-4-scout");
}

export function ModelBadge({ model }: ModelBadgeProps) {
  if (!model) return null;
  const short = shortName(model);
  const heavy = isHeavy(model);
  const classes = heavy
    ? "bg-amber-50 text-amber-800 ring-amber-200"
    : "bg-neutral-100 text-neutral-700 ring-neutral-200";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}
      title={`Last turn ran on ${model}`}
    >
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full ${
          heavy ? "bg-amber-500" : "bg-neutral-400"
        }`}
      />
      <span className="font-mono">{short}</span>
    </span>
  );
}
