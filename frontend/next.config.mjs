import { createRequire } from "module";

// Single source of truth for the displayed app version: package.json (kept in
// sync with tauri.conf.json / Cargo.toml). Inlined at build time so the About
// pane reads it instead of a hardcoded string that can drift.
const require = createRequire(import.meta.url);
const pkg = require("./package.json");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a fully static site (out/) so the Tauri desktop shell can bundle and
  // serve it with no Node server. Safe here because every page is client-side;
  // sessions are addressed via ?s=<id> on the static /chat page (no dynamic
  // route to pre-render). The dev workflow (`next dev`) is unaffected.
  output: "export",
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000",
    NEXT_PUBLIC_WS_BASE: process.env.NEXT_PUBLIC_WS_BASE ?? "ws://localhost:8000",
    NEXT_PUBLIC_APP_VERSION: pkg.version,
  },
};

export default nextConfig;
