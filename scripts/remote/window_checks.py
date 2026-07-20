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

  jar-pin --libs <build-libs-dir> --pin <jar_pin.yaml> [--accept-new-jar <prefix>]
      Runs on the ORCHESTRATOR (not the host): hash the build-path *shaded.jar and
      compare it to the EXPECTED sha256 in jar_pin.yaml BEFORE provision ships it.
      This is the expectation gate the old provision lacked (it blindly stamped
      whatever jar it shipped as trusted). Fail-closed: a missing pin file is a
      LOUD failure, never a skip.
        * match            -> exit 0, prints JARPIN_OK <sha16>
        * mismatch         -> exit 1, prints JARPIN_ERR + a loud block (both shas,
                              pin path, the two legitimate resolutions) to stderr
        * missing pin      -> exit 1, prints JARPIN_ERR pin-file-missing + how to
                              create it (fail-closed)
        * --accept-new-jar <prefix> matching the ACTUAL build-path sha REWRITES the
                              pin to the new sha (stamped auto-accept provenance) AND
                              appends an audit line to jar_pin_changelog.txt, then
                              exit 0 (JARPIN_ACCEPTED). A wrong/short prefix is refused.
"""

import argparse
import datetime
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


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_shaded_jar(libs):
    jars = glob.glob(os.path.join(libs, "*shaded.jar")) + glob.glob(os.path.join(libs, "*Shaded.jar"))
    jars = sorted(j for j in jars if os.path.isfile(j))
    return jars[0] if jars else None


def _load_pin_sha(pin_path):
    """Return the expected sha256 string from jar_pin.yaml, or None if unreadable/absent."""
    import yaml
    raw = _read(pin_path)
    if raw is None:
        return None
    doc = yaml.safe_load(raw) or {}
    if not isinstance(doc, dict):
        return None
    v = doc.get("sha256")
    if v is None:
        return None
    # str-coerce: an all-numeric sha would otherwise parse as a YAML int.
    return str(v).strip().lower() or None


def _render_pin_text(sha, provenance):
    return (
        "# jar_pin.yaml — the EXPECTED sha256 of the RuneLite shaded client jar that\n"
        "# provision is allowed to ship to a run host. See the git history / the\n"
        "# original header for the full rationale (defect: attempt #12, 2026-07-20).\n"
        "#\n"
        "# A mismatch fails LOUD. Resolutions: (a) restore the pinned jar from backup,\n"
        "# or (b) deliberately update this pin (back up the old jar first) via a\n"
        "# hand-edit or `mannyctl <host> window … --accept-new-jar <sha-prefix>`.\n"
        "#\n"
        "# provenance: %s\n"
        "sha256: %s\n" % (provenance, sha)
    )


def _utcnow_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_pin_change(pin_path, old_sha, new_sha):
    log_path = os.path.join(os.path.dirname(os.path.abspath(pin_path)), "jar_pin_changelog.txt")
    ts = _utcnow_str()
    line = "%s accept-new-jar old=%s new=%s pin=%s\n" % (
        ts, (old_sha or "MISSING")[:16], new_sha[:16], os.path.abspath(pin_path))
    try:
        with open(log_path, "a") as f:
            f.write(line)
    except OSError as e:  # noqa: BLE001
        sys.stderr.write("JARPIN warning: could not append audit log %s: %s\n" % (log_path, e))
    return log_path


def cmd_jar_pin(args):
    libs = args.libs
    pin_path = args.pin
    # Hash the build-path jar first (its absence is a distinct, actionable error).
    jar = _find_shaded_jar(libs)
    if jar is None:
        sys.stderr.write(
            "\n"
            "  JAR PIN GATE — FAIL: no *shaded.jar found in build-libs dir\n"
            "    build-libs : %s\n"
            "    (build the client on the orchestrator first, then re-run)\n\n" % libs)
        print("JARPIN_ERR no-shaded-jar:%s" % libs)
        return 1
    actual = _sha256_file(jar).lower()

    # Fail-closed: a missing/unreadable pin is a LOUD failure, never a skip.
    if not os.path.isfile(pin_path):
        sys.stderr.write(
            "\n"
            "  JAR PIN GATE — FAIL: pin file MISSING (fail-closed)\n"
            "    expected pin : %s\n"
            "    build jar    : %s\n"
            "    build sha256 : %s\n"
            "    To create it (only after you have REVIEWED this jar):\n"
            "      printf 'sha256: %s\\n' > %s\n"
            "    then add a provenance comment (manny commit + adoption date).\n\n"
            % (pin_path, jar, actual, actual, pin_path))
        print("JARPIN_ERR pin-file-missing:%s" % pin_path)
        return 1
    expected = _load_pin_sha(pin_path)
    if not expected:
        sys.stderr.write(
            "\n"
            "  JAR PIN GATE — FAIL: pin file has no readable `sha256:` value (fail-closed)\n"
            "    pin file : %s\n\n" % pin_path)
        print("JARPIN_ERR pin-sha-unreadable:%s" % pin_path)
        return 1

    if actual == expected:
        print("JARPIN_OK sha=%s jar=%s" % (actual[:16], os.path.basename(jar)))
        return 0

    # --- MISMATCH ---------------------------------------------------------
    accept = (args.accept_new_jar or "").strip().lower()
    if accept:
        # Override is allowed ONLY when the prefix matches the ACTUAL build jar
        # (so you cannot fat-finger-accept an unrelated jar), and it MUST leave a
        # trail: rewrites the pin + appends the changelog. Make the lazy path safe.
        if len(accept) < 8:
            sys.stderr.write(
                "\n  JAR PIN GATE — REFUSED --accept-new-jar: prefix too short "
                "(need >=8 hex chars, got %r)\n\n" % accept)
            print("JARPIN_ERR accept-prefix-too-short")
            return 1
        if not actual.startswith(accept):
            sys.stderr.write(
                "\n  JAR PIN GATE — REFUSED --accept-new-jar: prefix does not match the "
                "build jar\n    --accept-new-jar : %s\n    build sha256     : %s\n\n"
                % (accept, actual))
            print("JARPIN_ERR accept-prefix-mismatch")
            return 1
        provenance = ("AUTO-ACCEPTED via --accept-new-jar %s on %s — REVIEW REQUIRED: "
                      "replace with the real manny commit + adoption note"
                      % (accept, _utcnow_str()))
        try:
            with open(pin_path, "w") as f:
                f.write(_render_pin_text(actual, provenance))
        except OSError as e:  # noqa: BLE001
            sys.stderr.write("\n  JAR PIN GATE — FAIL: could not rewrite pin %s: %s\n\n" % (pin_path, e))
            print("JARPIN_ERR pin-rewrite-failed:%s" % pin_path)
            return 1
        log_path = _log_pin_change(pin_path, expected, actual)
        sys.stderr.write(
            "\n"
            "  JAR PIN GATE — NEW JAR ACCEPTED (pin updated, change logged)\n"
            "    old sha256 : %s\n"
            "    new sha256 : %s\n"
            "    pin file   : %s  (provenance stamped AUTO-ACCEPTED — fix it up)\n"
            "    audit log  : %s\n"
            "    Back up the OLD jar if you still have it; commit the pin change.\n\n"
            % (expected, actual, pin_path, log_path))
        print("JARPIN_ACCEPTED old=%s new=%s" % (expected[:16], actual[:16]))
        return 0

    sys.stderr.write(
        "\n"
        "  ==================  JAR PIN GATE — MISMATCH (REFUSING TO SHIP)  ==================\n"
        "    build jar    : %s\n"
        "    build sha256 : %s   <- what is about to be shipped\n"
        "    pinned sha256: %s   <- what jar_pin.yaml expects\n"
        "    pin file     : %s\n"
        "\n"
        "    The build-path jar is NOT the reviewed/pinned client. Do NOT ship it blind.\n"
        "    Two legitimate resolutions:\n"
        "      (a) RESTORE the pinned jar from backup (…/*.backup-%s) into the build-libs\n"
        "          dir so the build-path jar matches the pin again, then re-run; OR\n"
        "      (b) DELIBERATELY adopt this jar as a reviewed deploy: back up the OLD jar,\n"
        "          then update the pin — hand-edit sha256+provenance in %s, or re-run with\n"
        "          --accept-new-jar %s (rewrites the pin + logs the change).\n"
        "  =================================================================================\n\n"
        % (jar, actual, expected, pin_path, expected[:8], pin_path, actual[:12]))
    print("JARPIN_ERR jar-sha-mismatch build=%s pin=%s" % (actual[:16], expected[:16]))
    return 1


def cmd_selftest(args):
    """Offline self-check of the jar-pin logic against temp files. No host, no network."""
    import subprocess
    import tempfile
    failures = []

    def run(argv):
        return subprocess.run(
            [sys.executable, os.path.abspath(__file__)] + argv,
            capture_output=True, text=True)

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print("  SELFTEST %-28s %s %s" % (name, status, detail))
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        libs = os.path.join(td, "libs")
        os.makedirs(libs)
        jar = os.path.join(libs, "client-1.0-shaded.jar")
        with open(jar, "wb") as f:
            f.write(b"pretend-jar-bytes-v1")
        real_sha = _sha256_file(jar)
        pin = os.path.join(td, "jar_pin.yaml")

        # 1. correct pin -> pass
        with open(pin, "w") as f:
            f.write("sha256: %s\n" % real_sha)
        r = run(["jar-pin", "--libs", libs, "--pin", pin])
        check("correct-pin", r.returncode == 0 and "JARPIN_OK" in r.stdout, "(rc=%d)" % r.returncode)

        # 2. wrong-sha jar -> loud fail with BOTH shas printed
        wrong = "dead" * 16  # 64 hex chars, letters => a real string, not a YAML int
        with open(pin, "w") as f:
            f.write("sha256: %s\n" % wrong)
        r = run(["jar-pin", "--libs", libs, "--pin", pin])
        both = (real_sha[:16] in r.stdout or real_sha in r.stderr) and (wrong[:16] in (r.stdout + r.stderr))
        check("wrong-sha-loud-fail",
              r.returncode == 1 and "JARPIN_ERR jar-sha-mismatch" in r.stdout and "MISMATCH" in r.stderr and both,
              "(rc=%d)" % r.returncode)

        # 3. missing pin file -> loud fail-closed with create instructions
        missing = os.path.join(td, "nope.yaml")
        r = run(["jar-pin", "--libs", libs, "--pin", missing])
        check("missing-pin-fail-closed",
              r.returncode == 1 and "JARPIN_ERR pin-file-missing" in r.stdout and "fail-closed" in r.stderr,
              "(rc=%d)" % r.returncode)

        # 4. no jar in libs -> distinct fail
        empty = os.path.join(td, "emptylibs")
        os.makedirs(empty)
        r = run(["jar-pin", "--libs", empty, "--pin", pin])
        check("no-jar-fail", r.returncode == 1 and "JARPIN_ERR no-shaded-jar" in r.stdout, "(rc=%d)" % r.returncode)

        # 5. --accept-new-jar with matching prefix -> rewrites pin + logs, then passes
        with open(pin, "w") as f:
            f.write("sha256: %s\n" % wrong)
        r = run(["jar-pin", "--libs", libs, "--pin", pin, "--accept-new-jar", real_sha[:12]])
        rewritten = _load_pin_sha(pin) == real_sha
        logged = os.path.isfile(os.path.join(td, "jar_pin_changelog.txt"))
        check("accept-new-jar-rewrites",
              r.returncode == 0 and "JARPIN_ACCEPTED" in r.stdout and rewritten and logged,
              "(rc=%d rewritten=%s logged=%s)" % (r.returncode, rewritten, logged))
        # after accept, a plain re-check passes against the rewritten pin
        r = run(["jar-pin", "--libs", libs, "--pin", pin])
        check("post-accept-passes", r.returncode == 0 and "JARPIN_OK" in r.stdout, "(rc=%d)" % r.returncode)

        # 6. --accept-new-jar with WRONG prefix -> refused (cannot rubber-stamp blind)
        with open(pin, "w") as f:
            f.write("sha256: %s\n" % wrong)
        r = run(["jar-pin", "--libs", libs, "--pin", pin, "--accept-new-jar", "deadbeefcafe"])
        check("accept-wrong-prefix-refused",
              r.returncode == 1 and "accept-prefix-mismatch" in r.stdout and _load_pin_sha(pin) == wrong,
              "(rc=%d)" % r.returncode)

    print("SELFTEST %s (%d failing)" % ("OK" if not failures else "FAIL", len(failures)))
    return 0 if not failures else 1


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

    pj = sub.add_parser("jar-pin")
    pj.add_argument("--libs", required=True, help="build-libs dir to glob for *shaded.jar")
    pj.add_argument("--pin", required=True, help="path to jar_pin.yaml (expected sha256)")
    pj.add_argument("--accept-new-jar", default="", help="sha-prefix override: adopt the build jar (rewrites pin + logs)")
    pj.set_defaults(func=cmd_jar_pin)

    ps = sub.add_parser("selftest")
    ps.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
