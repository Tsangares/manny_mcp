#!/usr/bin/env python3
"""window_checks.py — on-host GATE 1 + GATE 4 checks for `mannyctl <host> window`.

Runs ON the target host, invoked over SSH by mannyctl's `window` subcommand with
plain argv. Lives here (not as an inline ssh one-liner) for the same reason as
window_login_gate.py: the logic (scan /proc, hash the jar, grep routine.py) is
multi-line and would trip the fish-login-shell ANSI-C-quoting hazard documented in
mannyctl/provision.sh if shipped as a heredoc. Plain argv sidesteps it entirely.
STDLIB ONLY except `yaml` (present in the host venv) for the config.yaml sha pin.

Subcommands (each prints one machine-greppable line + sets exit code):

  predecessor --account <acct>
      Is anything ALREADY driving <acct> on this host? Checks, WITHOUT ever
      self-matching (it inspects OTHER pids' /proc entries; its own cmdline holds
      'window_checks.py', never 'run_routine.py'/'watchdog.py'):
        * a java client  : /proc/<pid>/comm == 'java', '*shaded.jar' in its
                           cmdline, MANNY_ACCOUNT_ID=<acct> in its environ
        * run_routine.py : a python proc whose cmdline has run_routine.py + --account <acct>
        * watchdog.py    : a python proc whose cmdline has watchdog.py + --account <acct>
      exit 0 -> PREDECESSOR_CLEAR ; exit 1 -> PREDECESSOR_ALIVE <what:pid ...>

  assert-provision --account <acct> --staging <dir> --libs <dir> --routine <path>
      Post-provision host assertions:
        (a) config.yaml runelite_jar_sha256 pin present AND == sha256 of the host
            *shaded.jar (the launcher refuses any other jar)
        (b) mcptools/tools/routine.py has ZERO 'humanize' references
        (c) the routine file exists under staging
      exit 0 -> ASSERT_OK ... ; exit 1 -> ASSERT_ERR <reason>
"""

import argparse
import hashlib
import glob
import os
import sys


def _read(path, binary=False):
    try:
        with open(path, "rb" if binary else "r", errors=None if binary else "replace") as f:
            return f.read()
    except OSError:
        return None


def _proc_comm(pid):
    v = _read("/proc/%s/comm" % pid)
    return v.strip() if v else ""


def _proc_cmdline(pid):
    v = _read("/proc/%s/cmdline" % pid, binary=True)
    if not v:
        return ""
    return v.replace(b"\0", b" ").decode("utf-8", "replace")


def _proc_environ_account(pid):
    v = _read("/proc/%s/environ" % pid, binary=True)
    if not v:
        return None
    for kv in v.split(b"\0"):
        if kv.startswith(b"MANNY_ACCOUNT_ID="):
            return kv[len(b"MANNY_ACCOUNT_ID="):].decode("utf-8", "replace")
    return None


def _pids():
    for name in os.listdir("/proc"):
        if name.isdigit():
            yield name


def _driver_match(cmdline, script, account):
    """True iff cmdline runs <script> with --account <account> (either --account X or --account=X)."""
    if script not in cmdline:
        return False
    toks = cmdline.split()
    for i, t in enumerate(toks):
        if t == "--account" and i + 1 < len(toks) and toks[i + 1] == account:
            return True
        if t == "--account=" + account:
            return True
    return False


def cmd_predecessor(args):
    acct = args.account
    alive = []
    for pid in _pids():
        try:
            comm = _proc_comm(pid)
            if comm == "java":
                # A live client: comm is EXACTLY 'java' (never self-matches this
                # python), running the shaded jar, with MANNY_ACCOUNT_ID=<acct>.
                cmd = _proc_cmdline(pid)
                if "shaded.jar" in cmd and _proc_environ_account(pid) == acct:
                    alive.append("java_client:pid=%s" % pid)
            elif comm.startswith("python"):
                # The drivers are python. Gating on comm=='python*' means a bash/
                # ssh WRAPPER whose cmdline merely mentions 'run_routine.py' can
                # never be mistaken for one (comm=bash/sshd) — so this check cannot
                # self-match, even though the harness may wrap the invocation.
                cmd = _proc_cmdline(pid)
                if _driver_match(cmd, "run_routine.py", acct):
                    alive.append("run_routine.py:pid=%s" % pid)
                if _driver_match(cmd, "watchdog.py", acct):
                    alive.append("watchdog.py:pid=%s" % pid)
        except OSError:
            continue  # pid vanished mid-scan
    if alive:
        print("PREDECESSOR_ALIVE " + " ".join(alive))
        return 1
    print("PREDECESSOR_CLEAR")
    return 0


def cmd_assert_provision(args):
    os.chdir(args.staging) if os.path.isdir(args.staging) else None
    if not os.path.isdir(args.staging):
        print("ASSERT_ERR no-staging-dir:%s" % args.staging)
        return 1

    # (a) jar sha pin present + matches the host jar
    try:
        import yaml
        cfg = yaml.safe_load(_read("config.yaml") or "") or {}
    except Exception as e:  # noqa: BLE001 — any config read/parse failure is a gate fail
        print("ASSERT_ERR config.yaml-unreadable:%r" % e)
        return 1
    pin = (cfg.get("runelite_jar_sha256") or "").strip()
    if not pin:
        print("ASSERT_ERR jar-sha-pin-missing")
        return 1
    jars = glob.glob(os.path.join(args.libs, "*shaded.jar")) + glob.glob(os.path.join(args.libs, "*Shaded.jar"))
    jars = [j for j in jars if os.path.isfile(j)]
    if not jars:
        print("ASSERT_ERR no-shaded-jar-on-host:%s" % args.libs)
        return 1
    h = hashlib.sha256()
    with open(jars[0], "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if pin != actual:
        print("ASSERT_ERR jar-sha-mismatch pin=%s host=%s" % (pin[:16], actual[:16]))
        return 1

    # (b) routine.py has zero humanize refs
    rp = _read("mcptools/tools/routine.py")
    if rp is None:
        print("ASSERT_ERR routine.py-missing")
        return 1
    refs = rp.count("humanize")
    if refs:
        print("ASSERT_ERR routine.py-has-%d-humanize-refs" % refs)
        return 1

    # (c) the routine file exists
    if not os.path.isfile(args.routine):
        print("ASSERT_ERR routine-file-missing:%s" % args.routine)
        return 1

    print("ASSERT_OK jar_sha=%s routine.py=clean routine=%s" % (pin[:16], args.routine))
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="on-host window gate checks")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("predecessor")
    pp.add_argument("--account", required=True)
    pp.set_defaults(func=cmd_predecessor)

    pa = sub.add_parser("assert-provision")
    pa.add_argument("--account", required=True)
    pa.add_argument("--staging", required=True)
    pa.add_argument("--libs", required=True)
    pa.add_argument("--routine", required=True)
    pa.set_defaults(func=cmd_assert_provision)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
