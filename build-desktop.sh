#!/usr/bin/env bash
#
# build-desktop.sh — build the pMomentum macOS desktop app in one command.
#
# Produces an UNSIGNED Intel/x86_64 build:
#   - frontend/src-tauri/target/release/bundle/macos/pMomentum.app
#   - frontend/src-tauri/target/release/bundle/dmg/pMomentum_<ver>_x64.dmg   <-- install this
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
TARGET_TRIPLE="x86_64-apple-darwin"
SIDECAR="pmomentum-backend"

echo "==> [1/4] Freeze the Python backend into a one-file sidecar (PyInstaller)"
cd "$BACKEND"
if [ ! -x .venv/bin/pyinstaller ]; then
  echo "    pyinstaller not found — installing desktop extras (one-time)"
  .venv/bin/pip install -e ".[desktop]"
fi
.venv/bin/pyinstaller pmomentum.spec --noconfirm

echo "==> Self-check the frozen sidecar (crypto / trafilatura / bundled prompts+skills)"
"./dist/$SIDECAR" --selfcheck

echo "==> [2/4] Place the sidecar where Tauri expects it (target-triple suffix)"
mkdir -p "$FRONTEND/src-tauri/binaries"
cp -p "dist/$SIDECAR" "$FRONTEND/src-tauri/binaries/$SIDECAR-$TARGET_TRIPLE"

echo "==> [3/4] Build the Tauri app + .dmg (release; outer app left unsigned — see header)"
cd "$FRONTEND"
export PATH="$HOME/.cargo/bin:$PATH"
npx tauri build

echo "==> [4/4] Artifacts:"
BUNDLE="$FRONTEND/src-tauri/target/release/bundle"
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
