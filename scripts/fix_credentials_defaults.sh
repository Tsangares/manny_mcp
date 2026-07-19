#!/usr/bin/env bash
# fix_credentials_defaults.sh — repair ~/.manny/credentials.yaml after a Bolt
# re-import. [finding #5]
#
# STANDING HAZARD (has struck 5+ times): re-importing credentials via Bolt
# REGENERATES ~/.manny/credentials.yaml and RESETS `default:` to a BANNED alias
# (`new`/`newbakshesh`). Any unattended workflow that relies on the default
# account then silently starts on a banned account. This script makes the file
# sane again, idempotently:
#
#   1. Sets the top-level `default:` to a SAFE automation alias (punitpun by
#      default; override with --default <alias>). Refuses if that alias is not
#      present in the file (never point default: at a nonexistent account).
#   2. (Re)inserts the BANNED guard comment above `new:` and `newbakshesh:` if
#      absent (grep-guarded, so re-runs never duplicate it).
#
# Idempotent: running it twice is a no-op after the first. Preserves 600 perms.
# Never prints tokens.
#
# Usage: fix_credentials_defaults.sh [--default <alias>] [--file <path>]
set -euo pipefail

DEFAULT_ALIAS="punitpun"
CREDS="${MANNY_CREDENTIALS:-$HOME/.manny/credentials.yaml}"

usage() { echo "usage: $0 [--default <alias>] [--file <path>]"; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --default) DEFAULT_ALIAS="${2:?--default needs an alias}"; shift 2 ;;
    --file)    CREDS="${2:?--file needs a path}"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "fix_credentials: unknown arg: $1" >&2; usage 1 ;;
  esac
done

[ -f "$CREDS" ] || { echo "fix_credentials: no $CREDS (nothing to fix)" >&2; exit 1; }

# The safe target must exist as an alias (a "  <alias>:" line under accounts:),
# or we would set default: to a nonexistent account.
if ! grep -qE "^  ${DEFAULT_ALIAS}:" "$CREDS"; then
  echo "fix_credentials: target alias '${DEFAULT_ALIAS}' not present in ${CREDS} —" \
       "refusing to set a nonexistent default." >&2
  exit 1
fi

BANNED_COMMENT="  # BANNED alias — ban-detection gating ONLY; never start a live/automation run here."

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

awk -v target="$DEFAULT_ALIAS" -v banned="$BANNED_COMMENT" '
  # Insert the BANNED guard above new:/newbakshesh: unless the line we just
  # emitted is already a BANNED comment (idempotent).
  /^  (new|newbakshesh):[[:space:]]*$/ {
    if (prev !~ /BANNED/) { print banned }
  }
  # Rewrite the top-level default: line to the safe target.
  /^default:/ { print "default: " target; prev = "default: " target; next }
  { print; prev = $0 }
' "$CREDS" > "$tmp"

# If the file had no top-level default: line at all, add one.
if ! grep -qE "^default:" "$tmp"; then
  printf 'default: %s\n' "$DEFAULT_ALIAS" >> "$tmp"
fi

chmod 600 "$tmp"
mv "$tmp" "$CREDS"
trap - EXIT
echo "fix_credentials: default -> ${DEFAULT_ALIAS}; BANNED guards ensured on new/newbakshesh (${CREDS})."
