"use client";
import type { SessionMetadata } from "@/lib/types";

interface SkillBadgeProps {
  metadata?: SessionMetadata;
}

export function SkillBadge({ metadata }: SkillBadgeProps) {
  const skill = metadata?.active_skill;
  if (!skill) return null;
  const phase = metadata?.active_skill_phase;

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200"
      title={
        phase
          ? `Skill \`${skill}\` active — currently in the \`${phase}\` phase. Type /cancel-skill to exit.`
          : `Skill \`${skill}\` active. Type /cancel-skill to exit.`
      }
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500" />
      <span>
        Skill: <span className="font-mono">{skill}</span>
        {phase && (
          <>
            {" · "}
            <span className="text-indigo-600">{phase}</span>
          </>
        )}
      </span>
    </span>
  );
}
