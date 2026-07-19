#!/usr/bin/env python3
"""watchdog.py — unattended run-ledger + guardian for a remote manny grind.

Track F of the remote-run milestone. Runs ON the target host (e.g. diort),
setsid-detached alongside run_routine.py by `mannyctl <host> run`. Its job is to
notice, while nobody is watching, the three ways a long grind dies:

  1. THERMAL RUNAWAY — the box overheats. On two consecutive checks at/above the
     refuse threshold it SIGTERMs the run process (then the client) to protect the
     hardware, and records status=thermal_kill.
  2. FREEZE — the plugin state file stops updating (>120s stale) or a crash
     signature appears in the client log. This is recorded as needs_attention;
     the watchdog does NOT self-heal — the LLM driver reads the ledger and decides.
  3. NORMAL/ABNORMAL EXIT — the run process is gone. Recorded as completed (or
     dead, best-effort, if the last observation looked unhealthy) and the watchdog
     self-terminates.
  4. SUSPECTED BAN / TERMINAL LOGIN FAILURE (DEFECT-22b) — the plugin latches
     login.terminal_login_failure=true in the state file (a non-{2,4} login-error
     screen persisting across world-hop attempts without ever logging in). A banned/
     disabled/locked account can never log in, so continuing only hammers it: the
     watchdog records status=suspected_ban with a login_failure event and SIGTERMs the
     run (like a thermal kill — a terminal condition), then self-terminates. It does
     NOT relaunch or world-hop. Vision confirmation (analyze_screenshot) is the LLM
     driver's job when it reads the ledger — the watchdog is stdlib-only and has no
     vision on diort; the plugin latch is the authoritative in-process signal it acts on.
  5. LOGIN-BAN STALL (DEFECT-32) — the plugin latch above is DEFEATED when the client
     world-hops forever: login_index oscillates (e.g. 10<->14) so the in-plugin same-index
     streak never accumulates and terminal_login_failure never latches. Independently of
     the latch, the watchdog stalls a run that sits in a non-form login-error state past
     LOGIN_ERROR_MAX_SECONDS of continuous dwell OR more than LOGIN_ERROR_MAX_HOPS
     login-index flips (a world-hop proxy). Recorded as status=login_ban_stall with a
     login_stall event (dwell seconds + hop count), then SIGTERMs the run like a
     suspected_ban. Same do-NOT-relaunch/world-hop guidance applies.

It maintains one JSON run-record per run at /tmp/manny_runs/<run_id>.json, written
atomically (tmp + os.replace) every interval so a reader never sees a torn file.

STDLIB ONLY. It optionally imports mcptools.tools.monitoring.CRASH_PATTERNS when
launched from the repo root (as mannyctl does); if that import fails it falls back
to a vendored copy of the same signatures, so it never hard-depends on the repo.

Usage:
  watchdog.py --run-id <id> --account <acct> --routine <path> --run-pid <pid>
              [--client-pid <pid>] [--interval 60] [--temp-refuse 88]
              [--state-file PATH] [--log-file PATH] [--dry-run]

Timestamps are ISO-8601 UTC. Self-terminates when the run PID is gone.
"""

import argparse
import json
import os
import re
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone

RUNS_DIR = "/tmp/manny_runs"
STATE_STALE_S = 120          # state file older than this => needs_attention
LOG_TAIL_LINES = 200         # scan this many trailing log lines for crash sigs
THERMAL_CONSECUTIVE = 2      # consecutive over-temp checks before we kill
MAX_EVENTS = 500             # cap the events list so the record can't grow unbounded

# ---- DEFECT-32: oscillation-robust terminal-login (login-ban stall) --------------
# A banned account can never log in; the client world-hops and RETRIES forever. The
# in-plugin latch (terminal_login_failure) is defeated because its same-index streak
# resets on every world-hop (login_index oscillates e.g. 10<->14). So, independently of
# the latch, the watchdog stalls a run that SITS in a non-form login-error state: past
# LOGIN_ERROR_MAX_SECONDS of continuous error dwell, OR after more than
# LOGIN_ERROR_MAX_HOPS login-index flips within one error epoch (a world-hop proxy).
LOGIN_FORM_INDICES = frozenset({2, 4})   # documented username/password + authenticator forms
LOGIN_ERROR_MAX_SECONDS = 90.0           # continuous non-form login-error dwell => terminal
LOGIN_ERROR_MAX_HOPS = 6                 # login-index flips within one error epoch => terminal

# ---- crash signatures: prefer the repo's canonical list, fall back to vendored --
# This file lives at <repo>/scripts/remote/watchdog.py, so running it as a script
# puts scripts/remote (not the repo root) on sys.path[0] — mcptools wouldn't import.
# Add the repo root explicitly so the canonical CRASH_PATTERNS is used wherever we
# launch from; the vendored copy below is the graceful fallback if that still fails.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:
    from mcptools.tools.monitoring import CRASH_PATTERNS  # (pattern, description)
    _CRASH_SRC = "mcptools"
except Exception:
    _CRASH_SRC = "vendored"
    CRASH_PATTERNS = [
        ("Client error: map loading", "Map loading crash - client failed to load region data"),
        ("Client error", "Generic client crash"),
        ("OutOfMemoryError", "Out of memory - client ran out of heap space"),
        ("StackOverflowError", "Stack overflow - infinite recursion detected"),
        ("NullPointerException", "Null pointer exception in client"),
        ("TIMEOUT after", "Client thread timeout - game may be frozen"),
    ]

# Compile each signature as a regex; fall back to a literal-substring matcher if a
# pattern isn't valid regex. Each entry: (matcher(line)->bool, pattern, description).
def _build_matchers(patterns):
    out = []
    for pat, desc in patterns:
        try:
            rx = re.compile(pat)
            out.append((lambda line, rx=rx: rx.search(line) is not None, pat, desc))
        except re.error:
            out.append((lambda line, p=pat: p in line, pat, desc))
    return out

CRASH_MATCHERS = _build_matchers(CRASH_PATTERNS)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- thermal: port of client_remote.sh:57-88 pkg_temp_c fallback chain ----------
def pkg_temp_c():
    """Whole-degree package temp as int, or None if unreadable. Never raises."""
    # Primary: x86_pkg_temp thermal zone (laptop / most Intel).
    try:
        for type_file in _glob("/sys/class/thermal", "thermal_zone*", "type"):
            try:
                with open(type_file) as f:
                    if f.read().strip() != "x86_pkg_temp":
                        continue
                temp_file = os.path.join(os.path.dirname(type_file), "temp")
                milli = _read_int(temp_file)
                if milli is not None:
                    return milli // 1000
            except OSError:
                continue
    except OSError:
        pass
    # Fallback: coretemp hwmon "Package id 0" / "CPU Package" (diort's iMac).
    try:
        for label_file in _glob("/sys/class/hwmon", "hwmon*", "temp*_label"):
            try:
                with open(label_file) as f:
                    label = f.read().strip()
                if label.startswith("Package") or label == "CPU Package":
                    input_file = label_file[: -len("_label")] + "_input"
                    milli = _read_int(input_file)
                    if milli is not None:
                        return milli // 1000
            except OSError:
                continue
    except OSError:
        pass
    return None


def _glob(base, mid, leaf):
    """Tiny two-level glob without importing glob's fnmatch overhead surprises."""
    import glob as _g
    return _g.glob(os.path.join(base, mid, leaf))


def _read_int(path):
    try:
        with open(path) as f:
            v = f.read().strip()
        return int(v)
    except (OSError, ValueError):
        return None


def state_age_s(state_file):
    """Seconds since state_file was last modified, or None if it doesn't exist."""
    try:
        return max(0.0, time.time() - os.path.getmtime(state_file))
    except OSError:
        return None


def read_active_loop(state_file):
    """Return the state file's ``active_loop`` dict, or None. Never raises.

    DEFECT-26: the plugin publishes a live kill-loop status under ``active_loop``
    (null when idle). The watchdog reads it so it can tell a clean exit from a
    run that died while a loop is still grinding (an UNMANAGED grind)."""
    try:
        with open(state_file, "r", errors="replace") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    al = data.get("active_loop")
    return al if isinstance(al, dict) else None


def read_login_state(state_file):
    """Return the state file's ``login`` dict, or None. Never raises.

    DEFECT-22b: the plugin publishes a login/ban diagnostic section
    ``{game_state, login_index, terminal_login_failure, login_failure_message}``.
    Absent on pre-DEFECT-22b plugins -> None (the watchdog then simply never fires the
    suspected-ban path, preserving backward compatibility)."""
    try:
        with open(state_file, "r", errors="replace") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    login = data.get("login")
    return login if isinstance(login, dict) else None


def login_terminal_failure(login):
    """True iff the plugin latched a terminal login failure. Never raises.

    Keyed ONLY on the authoritative in-plugin latch ``terminal_login_failure`` — not on
    any driver-side heuristic. Missing/garbage section -> False (backward compatible)."""
    if not isinstance(login, dict):
        return False
    return bool(login.get("terminal_login_failure"))


def login_error_screen(login):
    """True iff `login` is a non-form login-error screen (DEFECT-32). Never raises.

    LOGIN_SCREEN on a readable, non-{2,4} login_index that has NOT logged in. Unlike
    login_terminal_failure this does NOT require the in-plugin latch — it is the raw
    error-state signal the oscillation-robust stall detector accrues dwell/hops over.
    Backward compatible: missing/garbage section, unreadable index (-1), or a real form
    index all return False."""
    if not isinstance(login, dict):
        return False
    if login.get("game_state") != "LOGIN_SCREEN":
        return False
    try:
        idx = int(login.get("login_index", -1))
    except (TypeError, ValueError):
        return False
    return idx >= 0 and idx not in LOGIN_FORM_INDICES


def pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else — still "alive"
    except (ValueError, TypeError):
        return False


def tail_crash_matches(log_file, seen):
    """Scan the last LOG_TAIL_LINES of log_file; return NEW (pattern, desc, line)
    matches not already in `seen` (a set of line hashes). Never raises."""
    matches = []
    if not log_file or not os.path.exists(log_file):
        return matches
    try:
        with open(log_file, "r", errors="replace") as f:
            lines = deque(f, maxlen=LOG_TAIL_LINES)
    except OSError:
        return matches
    for line in lines:
        line = line.rstrip("\n")
        for matcher, pat, desc in CRASH_MATCHERS:
            if matcher(line):
                key = hash((pat, line))
                if key not in seen:
                    seen.add(key)
                    matches.append((pat, desc, line[:200]))
                break  # one signature per line
    return matches


def default_state_file(account):
    return "/tmp/manny_%s_state.json" % account


def default_log_file(account):
    # Mirror client_remote.sh: account "new" -> /tmp/runelite.log, else suffixed.
    return "/tmp/runelite.log" if account == "new" else "/tmp/runelite_%s.log" % account


class RunRecord:
    """Owns the on-disk JSON ledger for one run. Every mutation flushed atomically."""

    def __init__(self, path, run_id, routine, account, run_pid, client_pid):
        self.path = path
        self.data = {
            "run_id": run_id,
            "routine": routine,
            "account": account,
            "run_pid": run_pid,
            "client_pid": client_pid,
            "started_at": now_iso(),
            "last_check": None,
            "temp_c": None,
            "state_age_s": None,
            "active_loop": None,
            "login": None,
            "status": "running",
            "crash_source": _CRASH_SRC,
            "events": [],
        }

    def event(self, kind, detail):
        self.data["events"].append({"ts": now_iso(), "kind": kind, "detail": detail})
        # keep the list bounded (retain most recent)
        if len(self.data["events"]) > MAX_EVENTS:
            self.data["events"] = self.data["events"][-MAX_EVENTS:]

    def update(self, **kw):
        self.data.update(kw)

    def flush(self):
        """Atomic write: temp file in the same dir + os.replace (same-fs rename)."""
        d = os.path.dirname(self.path)
        os.makedirs(d, exist_ok=True)
        tmp = "%s.tmp.%d" % (self.path, os.getpid())
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)


def parse_args(argv):
    p = argparse.ArgumentParser(description="unattended run-ledger + guardian")
    p.add_argument("--run-id", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--routine", required=True)
    p.add_argument("--run-pid", required=True, type=int)
    p.add_argument("--client-pid", type=int, default=None)
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--temp-refuse", type=int, default=88)
    p.add_argument("--state-file", default=None)
    p.add_argument("--log-file", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="observe + record only; never actually SIGTERM anything")
    return p.parse_args(argv)


def sigterm(pid):
    try:
        os.kill(int(pid), signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, ValueError, TypeError):
        return False


def main(argv):
    args = parse_args(argv)
    state_file = args.state_file or default_state_file(args.account)
    log_file = args.log_file or default_log_file(args.account)
    record_path = os.path.join(RUNS_DIR, "%s.json" % args.run_id)

    rec = RunRecord(record_path, args.run_id, args.routine, args.account,
                    args.run_pid, args.client_pid)
    rec.event("start", "watchdog up (interval=%ss refuse=%sC dry_run=%s state=%s log=%s crash_sigs=%s)"
              % (args.interval, args.temp_refuse, args.dry_run, state_file, log_file, _CRASH_SRC))
    rec.flush()

    seen_crash = set()
    over_temp_streak = 0
    stale_armed = True   # only fire a fresh "stale" event on each stale onset
    last_unhealthy = False
    # DEFECT-32 login-ban stall tracking (oscillation-robust; spans index changes).
    login_err_since = None
    login_err_prev_idx = None
    login_err_hops = 0

    while True:
        temp = pkg_temp_c()
        age = state_age_s(state_file)
        run_up = pid_alive(args.run_pid)
        client_up = pid_alive(args.client_pid) if args.client_pid else None
        active_loop = read_active_loop(state_file)
        login = read_login_state(state_file)

        rec.update(last_check=now_iso(),
                   temp_c=temp,
                   state_age_s=(round(age, 1) if age is not None else None),
                   active_loop=active_loop,
                   login=login)

        unhealthy = False

        # ---- 1. run process gone -> terminal, self-terminate --------------------
        if not run_up:
            # crash-in-flight or stale-at-exit -> best-effort "dead", else "completed"
            final_crashes = tail_crash_matches(log_file, seen_crash)
            for pat, desc, line in final_crashes:
                rec.event("crash", "%s :: %s" % (desc, line))

            # DEFECT-26: run process gone but the plugin-side kill loop is STILL
            # grinding -> the grind is now UNMANAGED. Never mark this "completed":
            # the whole point of Track-F is to notice exactly this. Record it so
            # the LLM driver can re-attach / STOP the loop.
            if active_loop is not None:
                rec.update(status="unmanaged_loop")
                rec.event("unmanaged_loop",
                          "run pid %s gone but active_loop still present: %s"
                          % (args.run_pid, active_loop))
                rec.flush()
                return 0

            unclean = bool(final_crashes) or last_unhealthy or (
                age is not None and age > STATE_STALE_S)
            status = "dead" if unclean else "completed"
            rec.update(status=status)
            rec.event("exit", "run pid %s gone; status=%s" % (args.run_pid, status))
            rec.flush()
            return 0

        # ---- 2. thermal guard (two consecutive over-temp checks) ----------------
        if temp is not None and temp >= args.temp_refuse:
            over_temp_streak += 1
            rec.event("temp_high", "package temp %sC >= refuse %sC (streak %d/%d)"
                      % (temp, args.temp_refuse, over_temp_streak, THERMAL_CONSECUTIVE))
            if over_temp_streak >= THERMAL_CONSECUTIVE:
                if args.dry_run:
                    rec.event("thermal_kill",
                              "[DRY-RUN] would SIGTERM run_pid=%s then client_pid=%s (temp %sC)"
                              % (args.run_pid, args.client_pid, temp))
                else:
                    ok_run = sigterm(args.run_pid)
                    rec.event("thermal_kill",
                              "SIGTERM run_pid=%s (%s) temp=%sC"
                              % (args.run_pid, "sent" if ok_run else "failed", temp))
                    if args.client_pid:
                        ok_cl = sigterm(args.client_pid)
                        rec.event("thermal_kill",
                                  "SIGTERM client_pid=%s (%s)"
                                  % (args.client_pid, "sent" if ok_cl else "failed"))
                rec.update(status="thermal_kill")
                rec.flush()
                return 0  # terminal — the run is being torn down
        else:
            over_temp_streak = 0

        # ---- 2b. suspected ban / terminal login failure (DEFECT-22b) -----------
        # The plugin has latched terminal_login_failure: a banned/disabled/locked
        # account that can never log in. STOP the run (terminal, like thermal); never
        # relaunch or world-hop. Record it so the LLM driver can vision-confirm + mark
        # the account. The plugin latch is the authoritative signal we act on.
        if login_terminal_failure(login):
            msg = (login or {}).get("login_failure_message") or "terminal login failure"
            gs = (login or {}).get("game_state")
            idx = (login or {}).get("login_index")
            detail = ("plugin latched terminal_login_failure (game_state=%s login_index=%s): %s"
                      % (gs, idx, msg))
            rec.event("login_failure", detail)
            if args.dry_run:
                rec.event("suspected_ban",
                          "[DRY-RUN] would SIGTERM run_pid=%s then client_pid=%s (%s)"
                          % (args.run_pid, args.client_pid, msg))
            else:
                ok_run = sigterm(args.run_pid)
                rec.event("suspected_ban",
                          "SIGTERM run_pid=%s (%s): %s"
                          % (args.run_pid, "sent" if ok_run else "failed", msg))
                if args.client_pid:
                    ok_cl = sigterm(args.client_pid)
                    rec.event("suspected_ban",
                              "SIGTERM client_pid=%s (%s)"
                              % (args.client_pid, "sent" if ok_cl else "failed"))
            rec.update(status="suspected_ban")
            rec.event("needs_attention",
                      "run stopped for suspected ban; do NOT relaunch/world-hop — "
                      "vision-confirm (analyze_screenshot) and mark the account")
            rec.flush()
            return 0  # terminal — the run is being torn down

        # ---- 2c. login-ban STALL: oscillation-robust terminal login (DEFECT-32) --
        # The client's own world-hopping oscillates login_index (e.g. 10<->14), so the
        # in-plugin same-index streak never latches terminal_login_failure and the run
        # would world-hop forever. Independently of the latch: if the client sits in ANY
        # non-form login-error state past LOGIN_ERROR_MAX_SECONDS, or the error index
        # flips more than LOGIN_ERROR_MAX_HOPS times, it is terminal — STOP cleanly.
        if login_error_screen(login):
            nowt = time.time()
            cur_idx = (login or {}).get("login_index")
            if login_err_since is None:
                login_err_since = nowt
                login_err_hops = 0
            elif login_err_prev_idx is not None and cur_idx != login_err_prev_idx:
                login_err_hops += 1
            login_err_prev_idx = cur_idx
            dwell = max(0.0, nowt - login_err_since)
            if dwell >= LOGIN_ERROR_MAX_SECONDS or login_err_hops >= LOGIN_ERROR_MAX_HOPS:
                trig = ("dwell %.0fs >= %.0fs" % (dwell, LOGIN_ERROR_MAX_SECONDS)
                        if dwell >= LOGIN_ERROR_MAX_SECONDS
                        else "hops %d >= %d" % (login_err_hops, LOGIN_ERROR_MAX_HOPS))
                rec.event("login_stall",
                          "non-form login-error state persisted (login_index=%s dwell=%.0fs "
                          "hops=%d): %s — client world-hopping without logging in, treating "
                          "as terminal" % (cur_idx, dwell, login_err_hops, trig))
                if args.dry_run:
                    rec.event("login_ban_stall",
                              "[DRY-RUN] would SIGTERM run_pid=%s then client_pid=%s (%s)"
                              % (args.run_pid, args.client_pid, trig))
                else:
                    ok_run = sigterm(args.run_pid)
                    rec.event("login_ban_stall",
                              "SIGTERM run_pid=%s (%s): %s"
                              % (args.run_pid, "sent" if ok_run else "failed", trig))
                    if args.client_pid:
                        ok_cl = sigterm(args.client_pid)
                        rec.event("login_ban_stall",
                                  "SIGTERM client_pid=%s (%s)"
                                  % (args.client_pid, "sent" if ok_cl else "failed"))
                rec.update(status="login_ban_stall")
                rec.event("needs_attention",
                          "run stopped: login-error stall (no login after %.0fs / %d world-hops); "
                          "do NOT relaunch/world-hop — vision-confirm (analyze_screenshot) and "
                          "mark the account" % (dwell, login_err_hops))
                rec.flush()
                return 0  # terminal — the run is being torn down
        else:
            # Reached a normal form / logged-in / non-login state — reset the epoch.
            login_err_since = None
            login_err_prev_idx = None
            login_err_hops = 0

        # ---- 3. freeze: stale state file ---------------------------------------
        if age is None:
            if stale_armed:
                rec.event("state_missing", "state file %s does not exist" % state_file)
                stale_armed = False
            unhealthy = True
        elif age > STATE_STALE_S:
            if stale_armed:
                rec.event("stale", "state file age %.1fs > %ds" % (age, STATE_STALE_S))
                stale_armed = False
            unhealthy = True
        else:
            stale_armed = True  # recovered — re-arm for the next onset

        # ---- 3b. freeze: crash signatures in the client log --------------------
        for pat, desc, line in tail_crash_matches(log_file, seen_crash):
            rec.event("crash", "%s :: %s" % (desc, line))
            unhealthy = True

        # ---- 3c. client process vanished while run continues -------------------
        if client_up is False:
            rec.event("client_dead", "client_pid %s no longer alive" % args.client_pid)
            unhealthy = True

        # needs_attention is advisory: record it, let the LLM driver decide.
        if unhealthy:
            if rec.data["status"] == "running":
                rec.update(status="needs_attention")
        last_unhealthy = unhealthy

        rec.flush()
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
