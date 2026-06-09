import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

// ESLint 9 flat config wrapping Next's shareable config (which is still
// eslintrc-style in Next 15), per the official Next.js migration recipe.
const compat = new FlatCompat({
  baseDirectory: dirname(fileURLToPath(import.meta.url)),
});

const config = [
  {
    ignores: [
      ".next/",
      "out/",
      "node_modules/",
      "next-env.d.ts",
      // Rust shell + its build artifacts — nothing lintable by ESLint.
      "src-tauri/",
    ],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default config;
