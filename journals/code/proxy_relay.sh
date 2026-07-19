#!/usr/bin/env bash
# proxy_relay.sh — start|stop|status a LOCAL pproxy SOCKS5 relay  [PROTOTYPE]
#
# Runs ON the client host (invoked over ssh by mannyctl, or directly by
# client_remote.sh just before a proxied launch). It accepts a NO-AUTH SOCKS5 on
# 127.0.0.1:${MANNY_SOCKS_PORT:-1080} and forwards to the dataimpulse residential
# proxy, handling the upstream auth. The JVM then routes ALL its TCP sockets
# (including the raw OSRS game socket on 43594) through this relay via
# -DsocksProxyHost/-DsocksProxyPort — see journals/2026-07-19_proxy_ip_wiring_plan.md.
#
# WHY a relay instead of proxychains or Java's own SOCKS auth:
#   - proxychains + Java NIO is documented broken (and not installed on diort).
#   - Java's SOCKS5 username/password auth is version-sensitive/awkward.
# A no-auth loopback relay sidesteps both: the JVM speaks plain SOCKS5 to
# 127.0.0.1 and pproxy owns the upstream credentials + (future) sticky session.
#
# The upstream secret is read at RUNTIME from ~/.manny/credentials.yaml
# (proxies.dataimpulse.socks5, stored as socks5h://user:pass@host:port) and
# converted to pproxy's `socks5://host:port#user:pass` upstream form. The secret
# is NEVER echoed by this script and never hard-coded.
#
# Config (env):
#   MANNY_SOCKS_PORT   loopback SOCKS5 port to listen on   (default: 1080)
#   REPO_DIR           manny_mcp repo (for venv python)     (default: script's ../..)
#   MANNY_CREDS        credentials.yaml path                (default: ~/.manny/credentials.yaml)
#
# Subcommands:
#   start    launch the relay (idempotent — no-op if already up on this port)
#   stop     stop the relay for this port
#   status   report up/down + an egress IP check through the relay

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

PORT="${MANNY_SOCKS_PORT:-1080}"
CREDS="${MANNY_CREDS:-$HOME/.manny/credentials.yaml}"

PIDFILE="/tmp/manny_pproxy_${PORT}.pid"
LOG="/tmp/manny_pproxy_${PORT}.log"

# Prefer the repo venv python (has pproxy + pyyaml); fall back to system python3.
PYBIN="$REPO_DIR/venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="python3"

usage() {
  cat <<'EOF'
Usage: proxy_relay.sh <start|stop|status>
  start   launch a no-auth SOCKS5 relay on 127.0.0.1:${MANNY_SOCKS_PORT:-1080}
          forwarding to proxies.dataimpulse (idempotent)
  stop    stop the relay on that port
  status  up/down + egress IP check through the relay
EOF
}

# relay_pid — echo the live relay pid for $PORT (from the pidfile), else nothing.
relay_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid; pid="$(cat "$PIDFILE" 2>/dev/null)"
  [ -n "${pid:-}" ] || return 1
  if kill -0 "$pid" 2>/dev/null; then echo "$pid"; return 0; fi
  return 1
}

# upstream_from_creds — read proxies.dataimpulse.socks5 and print pproxy's
# upstream form `socks5://host:port#user:pass`. The secret is printed ONLY to
# this function's stdout (captured into a local, never logged). Exits non-zero
# with a message on stderr if the key is missing.
upstream_from_creds() {
  "$PYBIN" - "$CREDS" <<'PY'
import sys, yaml
path = sys.argv[1]
try:
    data = yaml.safe_load(open(path)) or {}
except FileNotFoundError:
    sys.stderr.write("proxy_relay: no credentials file: %s\n" % path)
    sys.exit(2)
raw = ((data.get("proxies") or {}).get("dataimpulse") or {}).get("socks5")
if not raw:
    sys.stderr.write("proxy_relay: proxies.dataimpulse.socks5 not set in %s\n" % path)
    sys.exit(3)
# socks5h://user:pass@host:port -> socks5://host:port#user:pass
# rpartition('@') isolates the LAST '@' so an '@' inside the password is safe;
# partition(':') splits on the FIRST ':' so a ':' inside the password is safe.
after = raw.split("://", 1)[1]
userinfo, _, hostport = after.rpartition("@")
user, _, pw = userinfo.partition(":")
if not hostport or not user:
    sys.stderr.write("proxy_relay: malformed socks5 value (expected user:pass@host:port)\n")
    sys.exit(4)
print("socks5://%s#%s:%s" % (hostport, user, pw))
PY
}

cmd_start() {
  local pid
  if pid="$(relay_pid)"; then
    echo "relay already up on 127.0.0.1:${PORT} (pid=$pid) — no-op"
    return 0
  fi
  # Parse upstream secret into a local; never echo it.
  local upstream
  upstream="$(upstream_from_creds)" || {
    echo "ERROR: could not read dataimpulse upstream from $CREDS (see message above)." >&2
    echo "       Did you push creds to this host? (mannyctl <host> push-creds)" >&2
    return 1
  }
  [ -n "$upstream" ] || { echo "ERROR: empty upstream parsed from creds" >&2; return 1; }

  echo "starting SOCKS5 relay on 127.0.0.1:${PORT} -> dataimpulse (secret not shown) ..."
  : >"$LOG" 2>/dev/null || true
  # setsid + </dev/null + >log sever the tty so an ssh disconnect can't SIGHUP it.
  # We DON'T use `python -m pproxy`: pproxy 2.7.9 calls asyncio.get_event_loop()
  # at startup, which RAISES on Python 3.14 (the auto-create-in-main-thread
  # behaviour was removed). The shim pre-creates a loop so pproxy.server.main()
  # works on Python 3.10 through 3.14. `-v` makes pproxy log each connection.
  setsid "$PYBIN" -c '
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
from pproxy.server import main
main()
' -l "socks5://127.0.0.1:${PORT}" -r "$upstream" -v >"$LOG" 2>&1 </dev/null &
  local relay_started=$!
  disown
  echo "$relay_started" >"$PIDFILE"
  unset upstream   # drop the secret from the shell env asap

  # Readiness: a bad bind/upstream makes pproxy exit immediately. Wait until the
  # loopback port actually accepts a TCP connection (proves it's listening), or
  # fail if the process dies first.
  local waited=0
  while [ "$waited" -lt 20 ]; do
    if ! kill -0 "$relay_started" 2>/dev/null; then
      echo "ERROR: relay (pid=$relay_started) died immediately. Last log lines:" >&2
      tail -n 15 "$LOG" 2>/dev/null >&2 || true
      rm -f "$PIDFILE"
      return 1
    fi
    if timeout 1 bash -c "exec 3<>/dev/tcp/127.0.0.1/${PORT}" 2>/dev/null; then break; fi
    sleep 0.5; waited=$(( waited + 1 ))
  done
  echo "relay up on 127.0.0.1:${PORT} (pid=$relay_started, log=$LOG)"
  return 0
}

cmd_stop() {
  local pid
  if ! pid="$(relay_pid)"; then
    echo "no relay running on 127.0.0.1:${PORT} (nothing to stop)"
    rm -f "$PIDFILE"
    return 0
  fi
  echo "stopping relay pid=$pid (port ${PORT}) ..."
  kill -TERM "$pid" 2>/dev/null || true
  local waited=0
  while [ "$waited" -lt 8 ] && kill -0 "$pid" 2>/dev/null; do sleep 1; waited=$(( waited + 1 )); done
  if kill -0 "$pid" 2>/dev/null; then
    echo "  straggler, SIGKILL pid=$pid"; kill -KILL "$pid" 2>/dev/null || true; sleep 1
  fi
  rm -f "$PIDFILE"
  echo "relay stopped (port ${PORT})"
}

cmd_status() {
  local pid
  if pid="$(relay_pid)"; then
    echo "relay: UP on 127.0.0.1:${PORT} (pid=$pid, log=$LOG)"
  else
    echo "relay: DOWN on 127.0.0.1:${PORT}"
    return 0
  fi
  # Egress check: the exit IP as seen through the relay. Should be the residential
  # dataimpulse exit (~82.x / 74.x), NOT the home IP 96.39.231.108.
  echo -n "egress IP via relay: "
  local ip
  ip="$(curl -s --max-time 20 -x "socks5h://127.0.0.1:${PORT}" https://api.ipify.org 2>/dev/null)"
  if [ -n "$ip" ]; then
    echo "$ip"
    if [ "$ip" = "96.39.231.108" ]; then
      echo "  WARNING: egress is the HOME IP — relay is NOT changing the exit IP!"
    fi
  else
    echo "(egress check failed — relay may be starting, upstream unreachable, or no curl)"
  fi
}

main() {
  local sub="${1:-}"; [ -n "$sub" ] && shift || true
  case "$sub" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    -h|--help|help) usage; exit 0 ;;
    "") usage; exit 1 ;;
    *) echo "ERROR: unknown subcommand '$sub'" >&2; usage; exit 1 ;;
  esac
}
main "$@"
