"use client";

// Geometric wordmark/mark for pmomentum — a rounded square with a stylized
// "p" + upward (momentum) arrow. Recreated from the C8 design prototype.
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="0.75" y="0.75" width="30.5" height="30.5" rx="8" ry="8" fill="var(--accent)" />
      <rect x="9" y="9" width="3" height="17" rx="1.2" fill="var(--accent-fg)" />
      <path d="M12 11 H18 a5 5 0 0 1 0 10 H12 Z" fill="var(--accent-fg)" />
      <path
        d="M20.5 9.5 L24 9.5 L24 13 M24 9.5 L17.5 16"
        stroke="var(--accent-fg)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export function Wordmark({ size = 26 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <Mark size={size} />
      <span
        style={{ fontSize: size * 0.6, color: "var(--text)" }}
        className="font-semibold tracking-tight leading-none"
      >
        pmomentum
      </span>
    </div>
  );
}
