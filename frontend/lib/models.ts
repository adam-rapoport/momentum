// Model display helpers shared by the toolbar chip and anywhere else a
// model id needs a short friendly name.

// Map full model IDs to short friendly names. Unknown models fall through
// to the last `/`-separated segment so the label is still useful.
export function modelShortName(model: string): string {
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

export function isHeavyModel(model: string): boolean {
  // Any model that isn't the default Scout is styled as "heavy".
  return !model.includes("llama-4-scout");
}
