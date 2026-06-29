#!/usr/bin/env bash
#
# build-desktop.sh — build the pMomentum macOS desktop app in one command.
#
# Produces an UNSIGNED build for the architecture of the machine running this
# script (the dmg/app names carry the real target triple):
#   - frontend/src-tauri/target/<triple>/release/bundle/macos/pMomentum.app
#   - frontend/src-tauri/target/<triple>/release/bundle/dmg/pMomentum_<ver>_<arch>.dmg
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
# IMPORTANT: the outer .app is intentionally left UNSIGNED. The embedded backend
# (a PyInstaller one-file binary) is already ad-hoc signed by PyInstaller in a way
# that's internally consistent, so it runs. Do NOT add bundle.macOS.signingIdentity
# here to ad-hoc re-sign the app: that re-signs the backend binary but NOT the Python
# library bundled inside it, and macOS Library Validation then refuses to launch the
# backend ("different Team IDs"). Real code signing + notarization come in a later
# sprint and must use a Developer ID cert + the `com.apple.security.cs.disable-library-
# validation` entitlement (or switch PyInstaller to onedir mode). See INSTALL.md.
#
# Usage:  ./build-desktop.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
SIDECAR="pmomentum-backend"

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
.venv/bin/pyinstaller pmomentum.spec --noconfirm

echo "==> Self-check the frozen sidecar (crypto / trafilatura / migrations / SDKs / bundled data)"
"./dist/$SIDECAR" --selfcheck

echo "==> [2/4] Place the sidecar where Tauri expects it (target-triple suffix)"
mkdir -p "$FRONTEND/src-tauri/binaries"
cp -p "dist/$SIDECAR" "$FRONTEND/src-tauri/binaries/$SIDECAR-$TARGET_TRIPLE"

echo "==> [3/4] Build the Tauri bundle(s): $BUNDLES (release; outer app left unsigned — see header)"
cd "$FRONTEND"
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build --target "$TARGET_TRIPLE" --bundles "$BUNDLES"

echo "==> [4/4] Artifacts:"
BUNDLE="$FRONTEND/src-tauri/target/$TARGET_TRIPLE/release/bundle"
APP_PATH="$(ls -d "$BUNDLE/macos/"*.app 2>/dev/null | head -n1 || true)"
DMG_PATH="$(ls "$BUNDLE/dmg/"*.dmg 2>/dev/null | head -n1 || true)"
echo "    APP: ${APP_PATH:-<none>}"
echo "    DMG: ${DMG_PATH:-<none>}"

if [ -n "${APP_PATH:-}" ]; then
  echo "==> Verify the embedded backend kept PyInstaller's signature (expect Signature=adhoc)"
  codesign -dvv "$APP_PATH/Contents/MacOS/pmomentum-backend" 2>&1 | grep -iE "Identifier|Signature|Format" || true
fi

echo ""
echo "==> Done. Install the .dmg above (drag pMomentum into Applications)."
echo "    First launch may show an 'unidentified developer' prompt — see INSTALL.md."
