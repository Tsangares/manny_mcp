#!/usr/bin/env bash
# tree_lock.sh — advisory ownership lockfile for contended git trees.
#
# Retrospective item 1 (journals/2026-07-19_methods_retrospective.md, "shortlist" #1): the
# branch-collision and dual-driver-ghost incidents both cost real cleanup time because
# one-tree-one-agent was a MEMORY rule, not a mechanical one. This makes it mechanical-ish:
# a small on-disk record naming which agent currently owns a tree. It is CHECKED BY CONVENTION
# (agents are expected to call `check` before claiming and before committing), not enforced by
# a git hook — see the handoff's delegation section for the expected usage pattern.
#
# Lock files: /tmp/manny_tree_locks/<tree>.lock  (one line: "<agent> <ISO8601-UTC-timestamp>")
#
# Usage:
#   tree_lock.sh claim   <tree> <agent>   — claim <tree> for <agent> (fails if held by someone else)
#   tree_lock.sh release <tree> <agent>   — release <tree> (fails if held by someone else)
#   tree_lock.sh check   <tree>           — print current holder + age, or "unclaimed"; exit 0 always
#
# <tree> is just a label (e.g. "manny", "manny_mcp") — this script does not touch git itself.

set -euo pipefail

LOCK_DIR="${MANNY_TREE_LOCK_DIR:-/tmp/manny_tree_locks}"
mkdir -p "$LOCK_DIR"

usage() {
  echo "usage: tree_lock.sh claim|release <tree> <agent>" >&2
  echo "       tree_lock.sh check <tree>" >&2
  exit 1
}

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

lock_file() { echo "$LOCK_DIR/$1.lock"; }

cmd="${1:-}"; tree="${2:-}"
[ -n "$cmd" ] && [ -n "$tree" ] || usage

case "$cmd" in
  claim)
    agent="${3:-}"; [ -n "$agent" ] || usage
    f="$(lock_file "$tree")"
    if [ -f "$f" ]; then
      holder="$(cut -d' ' -f1 "$f")"
      if [ "$holder" != "$agent" ]; then
        echo "REFUSED: '$tree' already claimed by '$holder' ($(cut -d' ' -f2 "$f"))" >&2
        echo "  (stale? verify the holder is actually dead before overwriting: rm '$f' then retry)" >&2
        exit 1
      fi
    fi
    echo "$agent $(now)" > "$f"
    echo "claimed: $tree -> $agent"
    ;;
  release)
    agent="${3:-}"; [ -n "$agent" ] || usage
    f="$(lock_file "$tree")"
    if [ -f "$f" ]; then
      holder="$(cut -d' ' -f1 "$f")"
      if [ "$holder" != "$agent" ]; then
        echo "REFUSED: '$tree' is held by '$holder', not '$agent' — not releasing" >&2
        exit 1
      fi
      rm -f "$f"
    fi
    echo "released: $tree"
    ;;
  check)
    f="$(lock_file "$tree")"
    if [ -f "$f" ]; then
      echo "$tree: held by $(cat "$f")"
    else
      echo "$tree: unclaimed"
    fi
    ;;
  *)
    usage
    ;;
esac
