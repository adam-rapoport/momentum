import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-ui)", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        pixel: ["var(--font-pixel)", "monospace"],
      },
      colors: {
        app: "var(--bg-app)",
        panel: "var(--bg-panel)",
        surface: "var(--bg-surface)",
        raised: "var(--bg-raised)",
        inset: "var(--bg-inset)",
        ink: {
          DEFAULT: "var(--text)",
          muted: "var(--text-muted)",
          dim: "var(--text-dim)",
        },
        line: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
          faint: "var(--border-faint)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          bright: "var(--accent-bright)",
          fg: "var(--accent-fg)",
          tint: "var(--accent-tint)",
          "tint-2": "var(--accent-tint-2)",
          text: "var(--accent-text)",
        },
        warn: { DEFAULT: "var(--warn)", soft: "var(--warn-soft)" },
        danger: { DEFAULT: "var(--danger)", soft: "var(--danger-soft)" },
        ok: { DEFAULT: "var(--ok)", soft: "var(--ok-soft)" },
      },
      boxShadow: {
        card: "var(--shadow-card)",
        composer: "var(--shadow-composer)",
        pop: "var(--shadow-pop)",
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "10px",
        lg: "14px",
        xl: "20px",
      },
    },
  },
  plugins: [],
};

export default config;
