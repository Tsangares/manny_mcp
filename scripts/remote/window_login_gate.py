#!/usr/bin/env python3
"""window_login_gate.py — GATE 5 login/DEFECT-32 gate for `mannyctl <host> window`.

Runs ON the target host (same box as the client + its /tmp IPC files), invoked
over SSH by mannyctl's `window` subcommand AFTER client_remote.sh has launched the
client. It polls the account's plugin state file until the client is confirmed
LOGGED_IN with a real player location, and hard-fails LOUDLY the moment a terminal
login condition appears — so an unattended run never grinds against a banned/looping
account.

Why a script (not an inline ssh one-liner): the gate needs a poll loop + login-hop
counting, and shipping that as multi-line python through the fish login shell on the
remote hosts (diort/llama/mat) trips the ANSI-C-quoting hazard documented in
mannyctl/provision.sh. The manny_mcp rsync (provision, GATE 4) already deploys this
file to every host, so `window` just invokes it by path. STDLIB ONLY.

Gate outcomes (machine-greppable; one WINDOW_LOGIN line + exit code):
  exit 0  PASS         LOGGED_IN and player.location is non-null
  exit 3  BAN          plugin latched login.terminal_login_failure (DEFECT-22b) —
                       a banned/disabled/locked account that can never log in
  exit 4  WORLDHOP     login_index flipped more than --max-hops times (DEFECT-32):
                       the client is world-hopping forever without logging in
  exit 5  TIMEOUT      no LOGGED_IN within --timeout seconds
  exit 2  usage/other

State schema consumed (GameEngine.buildState): state["login"] =
{game_state, login_index, terminal_login_failure, login_failure_message};
state["player"]["location"] = {x, y, plane} (present only once localPlayer exists).
"""

import argparse
import json
import os
import sys
import time


def default_state_file(account):
    return "/tmp/manny_%s_state.json" % account


def default_log_file(account):
    # Mirror client_remote.sh: account "new" -> /tmp/runelite.log, else suffixed.
    return "/tmp/runelite.log" if account == "new" else "/tmp/runelite_%s.log" % account


def read_state(path):
    """Return the parsed state dict, or None if unreadable/torn/absent. Never raises."""
    try:
        with open(path, "r", errors="replace") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def player_location(state):
    """Return (x, y, plane) if the state carries a real player location, else None."""
    if not isinstance(state, dict):
        return None
    player = state.get("player")
    if not isinstance(player, dict):
        return None
    loc = player.get("location")
    if not isinstance(loc, dict):
        return None
    x, y = loc.get("x"), loc.get("y")
    if x is None or y is None:
        return None
    return (x, y, loc.get("plane"))


def login_section(state):
    if not isinstance(state, dict):
        return {}
    login = state.get("login")
    return login if isinstance(login, dict) else {}


def emit(status, detail):
    print("WINDOW_LOGIN %s: %s" % (status, detail))
    sys.stdout.flush()


def main(argv):
    p = argparse.ArgumentParser(description="window GATE 5 login/DEFECT-32 gate")
    p.add_argument("--account", required=True)
    p.add_argument("--state-file", default=None)
    p.add_argument("--log-file", default=None)
    p.add_argument("--timeout", type=float, default=90.0,
                   help="max seconds to wait for LOGGED_IN (default: %(default)s)")
    p.add_argument("--max-hops", type=int, default=3,
                   help="abort if login_index flips more than this many times (DEFECT-32)")
    p.add_argument("--poll", type=float, default=2.0, help="poll interval seconds")
    args = p.parse_args(argv)

    state_file = args.state_file or default_state_file(args.account)
    log_file = args.log_file or default_log_file(args.account)

    deadline = time.time() + args.timeout
    prev_idx = None
    hops = 0
    last_gs = None
    saw_state = False

    while True:
        state = read_state(state_file)
        if state is not None:
            saw_state = True
            login = login_section(state)
            gs = login.get("game_state")
            idx = login.get("login_index")
            last_gs = gs

            # --- terminal ban latch (DEFECT-22b): authoritative in-plugin signal ---
            if login.get("terminal_login_failure"):
                msg = login.get("login_failure_message") or "terminal login failure"
                emit("BAN", "plugin latched terminal_login_failure "
                            "(game_state=%s login_index=%s): %s" % (gs, idx, msg))
                return 3

            # --- LOGGED_IN + real location => PASS ---
            if gs == "LOGGED_IN":
                loc = player_location(state)
                if loc is not None:
                    emit("PASS", "LOGGED_IN at location=%s,%s,%s (login_index=%s)"
                                 % (loc[0], loc[1], loc[2], idx))
                    return 0
                # logged in but location not yet populated — keep polling briefly

            # --- world-hop counter (DEFECT-32): login_index oscillation while NOT in ---
            if idx is not None and idx != prev_idx and prev_idx is not None and gs != "LOGGED_IN":
                hops += 1
                if hops > args.max_hops:
                    emit("WORLDHOP", "login_index flipped %d times (> max-hops %d) without "
                                     "logging in (last game_state=%s login_index=%s) — client "
                                     "world-hopping; refusing to run"
                                     % (hops, args.max_hops, gs, idx))
                    return 4
            if idx is not None:
                prev_idx = idx

        if time.time() >= deadline:
            if not saw_state:
                emit("TIMEOUT", "no state file at %s within %.0fs (client never wrote state — "
                                "check the client log %s)" % (state_file, args.timeout, log_file))
            else:
                emit("TIMEOUT", "no LOGGED_IN within %.0fs (last game_state=%s, hops=%d)"
                                % (args.timeout, last_gs, hops))
            return 5

        time.sleep(max(0.5, args.poll))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
