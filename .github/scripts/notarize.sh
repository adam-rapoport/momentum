#!/usr/bin/env bash
# Notarize a .zip or .dmg with retry-hardened submit + poll.
#
# Why not `notarytool submit --wait`: on hosted runners notarytool's built-in
# wait dies on transient network errors ("Internet connection appears to be
# offline", "The request timed out") even when the submission itself is fine —
# observed twice on the first release runs (2026-07-04). So we submit async,
# keep the submission id, and poll `notarytool info` ourselves, tolerating
# consecutive poll failures instead of giving up on the first blip.
#
# Usage: notarize.sh <path-to-zip-or-dmg>
# Env:   APPLE_ID, APPLE_PASSWORD, APPLE_TEAM_ID
set -euo pipefail

FILE="$1"
AUTH=(--apple-id "$APPLE_ID" --password "$APPLE_PASSWORD" --team-id "$APPLE_TEAM_ID")

json_field() { /usr/bin/python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

# --- submit (async), retrying the upload itself up to 3x --------------------
SUBMISSION_ID=""
for attempt in 1 2 3; do
  if OUT="$(xcrun notarytool submit "$FILE" "${AUTH[@]}" --output-format json 2>/dev/null)"; then
    SUBMISSION_ID="$(echo "$OUT" | json_field id)"
    break
  fi
  echo "submit attempt $attempt failed"
  if [ "$attempt" = 3 ]; then
    echo "::error::notarization upload failed after 3 attempts"
    exit 1
  fi
  sleep 45
done
echo "submitted $(basename "$FILE") -> submission $SUBMISSION_ID"

# --- poll until Accepted / Invalid, riding out transient poll errors --------
CONSECUTIVE_FAILS=0
for i in $(seq 1 90); do # 90 x 30s = up to 45 minutes (first-ever
  sleep 30               # submissions on a new account can be slow)
  if INFO="$(xcrun notarytool info "$SUBMISSION_ID" "${AUTH[@]}" --output-format json 2>/dev/null)"; then
    CONSECUTIVE_FAILS=0
    STATUS="$(echo "$INFO" | json_field status)"
    echo "[$i] status: $STATUS"
    case "$STATUS" in
      Accepted)
        exit 0
        ;;
      Invalid | Rejected)
        echo "::error::notarization $STATUS — fetching log"
        xcrun notarytool log "$SUBMISSION_ID" "${AUTH[@]}" || true
        exit 1
        ;;
    esac # "In Progress" -> keep polling
  else
    CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
    echo "[$i] poll error ($CONSECUTIVE_FAILS consecutive)"
    if [ "$CONSECUTIVE_FAILS" -ge 10 ]; then
      echo "::error::10 consecutive poll failures — giving up"
      exit 1
    fi
  fi
done
echo "::error::notarization still In Progress after 45 minutes"
exit 1
