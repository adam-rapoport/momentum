#!/usr/bin/env bash
#
# build-desktop.sh — build the Momentum macOS desktop app in one command.
#
# Produces an UNSIGNED build for the architecture of the machine running this
# script (the dmg/app names carry the real target triple):
#   - frontend/src-tauri/target/<triple>/release/bundle/macos/Momentum.app
#   - frontend/src-tauri/target/<triple>/release/bundle/dmg/Momentum_<ver>_<arch>.dmg
#
# ARCHITECTURE: PyInstaller can only freeze the Python backend for the HOST
# architecture — there is no cross-compile. The script derives the target
# triple from the local Rust toolchain (`rustc -vV`), names the sidecar to
# match, and passes the same `--target` to `tauri build`, so the artifact is
# always labeled with what it actually contains:
#   - run on an Intel Mac        -> x86_64-apple-darwin build (runs on Apple
#     Silicon via Rosetta 2)
#   - run on an Apple Silicon Mac -> aarch64-apple-darwin (native) build
# A native Apple Silicon build therefore requires running this whole script on
# Apple Silicon hardware. (A universal binary would need per-arch PyInstaller
# runs + `lipo` and is not wired up yet.)
#
# REPRODUCIBILITY: backend Python deps are installed from the pinned
# backend/requirements-desktop.lock (regenerate with
# backend/scripts/regen-desktop-lock.sh after changing pyproject.toml deps),
# so two builds of the same commit freeze the same dependency set.
#
# VERSION: frontend/src-tauri/tauri.conf.json `version` is the source of truth
# for the app/dmg version. Keep backend/pyproject.toml, frontend/package.json
# and frontend/src-tauri/Cargo.toml in sync with it (all 0.1.0 today).
#
# SIGNING (env-driven, dormant by default): with no Apple env vars set this
# produces the same UNSIGNED build as always — the embedded PyInstaller backend
# keeps its own internally-consistent ad-hoc signature and runs fine. Do NOT
# add bundle.macOS.signingIdentity to tauri.conf.json: a non-Developer-ID
# re-sign hits macOS Library Validation ("different Team IDs") and kills the
# backend at launch. Real signing activates ONLY when Tauri's standard env vars
# are present (APPLE_CERTIFICATE, APPLE_CERTIFICATE_PASSWORD,
# APPLE_SIGNING_IDENTITY, and APPLE_ID/APPLE_PASSWORD/APPLE_TEAM_ID for
# notarization) — together with src-tauri/entitlements.plist, whose
# disable-library-validation entitlement is what makes a Developer-ID-signed
# app tolerate the PyInstaller backend. See .github/workflows/release.yml.
#
# UPDATER ARTIFACTS: tauri.conf.json sets bundle.createUpdaterArtifacts, which
# needs the updater signing key. The script auto-loads it from
# ~/Documents/momentum-release-keys/updater.key (Adam's machine) or the
# TAURI_SIGNING_PRIVATE_KEY(-_PATH) env (CI secret); with neither present it
# disables updater artifacts for that build instead of failing.
#
# Usage:  ./build-desktop.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
SIDECAR="momentum-backend"

# Which Tauri bundle targets to produce. Default = app + dmg (the local
# one-command experience). CI sets PM_BUNDLES=app: Tauri's bundle_dmg.sh needs
# a Finder/GUI session to lay out the .dmg window and fails on headless
# runners, so CI builds the .app here and wraps its own plain, headless-safe
# .dmg with hdiutil instead (see .github/workflows/desktop-build.yml).
BUNDLES="${PM_BUNDLES:-app,dmg}"

# Derive the target triple from the host toolchain so the sidecar name and the
# Tauri target always match what PyInstaller actually built (PyInstaller has no
# cross-compile — it freezes for the host arch, full stop).
TARGET_TRIPLE="$(rustc -vV 2>/dev/null | sed -n 's/^host: //p' || true)"
if [ -z "$TARGET_TRIPLE" ]; then
  case "$(uname -m)" in
    arm64 | aarch64) TARGET_TRIPLE="aarch64-apple-darwin" ;;
    x86_64) TARGET_TRIPLE="x86_64-apple-darwin" ;;
    *)
      echo "ERROR: cannot determine target triple (rustc not found, unknown arch '$(uname -m)')" >&2
      exit 1
      ;;
  esac
fi
echo "==> Building for target: $TARGET_TRIPLE (host arch — PyInstaller cannot cross-compile)"

echo "==> [1/4] Freeze the Python backend into a one-file sidecar (PyInstaller)"
cd "$BACKEND"
if [ ! -x .venv/bin/python ]; then
  echo "    no venv found — creating backend/.venv"
  python3.12 -m venv .venv
fi
# Pinned, reproducible dependency set: install exactly the lockfile, then the
# project itself without re-resolving (--no-deps keeps the pins authoritative).
.venv/bin/pip install -q -r requirements-desktop.lock
.venv/bin/pip install -q --no-deps -e .
.venv/bin/pyinstaller momentum.spec --noconfirm

echo "==> Self-check the frozen sidecar (crypto / trafilatura / migrations / SDKs / bundled data)"
"./dist/$SIDECAR" --selfcheck

echo "==> [2/4] Place the sidecar where Tauri expects it (target-triple suffix)"
mkdir -p "$FRONTEND/src-tauri/binaries"
cp -p "dist/$SIDECAR" "$FRONTEND/src-tauri/binaries/$SIDECAR-$TARGET_TRIPLE"

echo "==> [3/4] Build the Tauri bundle(s): $BUNDLES"
cd "$FRONTEND"
export PATH="$HOME/.cargo/bin:$PATH"

# Updater artifact signing key: env (CI) > local key file > disable artifacts.
LOCAL_UPDATER_KEY="$HOME/Documents/momentum-release-keys/updater.key"
UPDATER_ARGS=()
if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ] && [ -f "$LOCAL_UPDATER_KEY" ]; then
  # Pass the key CONTENTS: the CLI's updater signer reads the private key from
  # TAURI_SIGNING_PRIVATE_KEY (the _PATH variant is not honored by every
  # version — verified 2026-07 with CLI 2.x: path-only fails with "A public
  # key has been found, but no private key").
  TAURI_SIGNING_PRIVATE_KEY="$(cat "$LOCAL_UPDATER_KEY")"
  export TAURI_SIGNING_PRIVATE_KEY
fi
if [ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  # Even a passwordless key needs the password var set (to empty) or the CLI
  # tries to prompt a TTY and dies headless ("Device not configured").
  export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}"
fi
if [ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
  echo "    updater artifacts: ON (signing key found)"
else
  echo "    updater artifacts: OFF (no updater signing key — fine for test builds)"
  UPDATER_ARGS=(--config '{"bundle":{"createUpdaterArtifacts":false}}')
fi

if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
  echo "    code signing: ON ($APPLE_SIGNING_IDENTITY; notarization $([ -n "${APPLE_ID:-}" ] && echo ON || echo OFF))"
else
  echo "    code signing: OFF (unsigned build — see header)"
fi

# ${arr[@]+...} keeps macOS's bash 3.2 happy when the array is empty (set -u).
npx tauri build --target "$TARGET_TRIPLE" --bundles "$BUNDLES" ${UPDATER_ARGS[@]+"${UPDATER_ARGS[@]}"}

echo "==> [4/4] Artifacts:"
BUNDLE="$FRONTEND/src-tauri/target/$TARGET_TRIPLE/release/bundle"
APP_PATH="$(ls -d "$BUNDLE/macos/"*.app 2>/dev/null | head -n1 || true)"
DMG_PATH="$(ls "$BUNDLE/dmg/"*.dmg 2>/dev/null | head -n1 || true)"
echo "    APP: ${APP_PATH:-<none>}"
echo "    DMG: ${DMG_PATH:-<none>}"

if [ -n "${APP_PATH:-}" ]; then
  echo "==> Embedded backend signature (adhoc when unsigned; Developer ID when signed)"
  codesign -dvv "$APP_PATH/Contents/MacOS/momentum-backend" 2>&1 | grep -iE "Identifier|Signature|Format" || true
fi

echo ""
echo "==> Done. Install the .dmg above (drag Momentum into Applications)."
echo "    First launch may show an 'unidentified developer' prompt — see INSTALL.md."
