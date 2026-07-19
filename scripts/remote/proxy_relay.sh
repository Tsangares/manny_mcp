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
# The upstream secret is read at RUNTIME by socks_relay.py itself from the creds
# file (proxies.dataimpulse.socks5, stored as socks5h://user:pass@host:port). The
# relay defaults to ~/.manny/proxies.yaml (Bolt-immune) and falls back to
# ~/.manny/credentials.yaml. The secret is read INSIDE the relay process — never
# echoed by this script, never on argv, never hard-coded.
#
# HISTORY: this relay used to shell out to `pproxy`, but pproxy's `-r` URI parser
# REJECTS the dataimpulse session/geo token in the username (`__cr.us;sessid.<id>`
# — both the `.` and the `;` blow up its grammar). Since a live OSRS session needs
# BOTH a US geo-pin and a sticky session, the token is mandatory, so pproxy was
# swapped for scripts/remote/socks_relay.py (a dependency-free asyncio SOCKS5
# forwarder that passes the token through verbatim). See
# journals/2026-07-19_mat_sticky_proxy_bringup.md.
#
# Config (env):
#   MANNY_SOCKS_PORT   loopback SOCKS5 port to listen on   (default: 1080)
#   REPO_DIR           manny_mcp repo (for venv python)     (default: script's ../..)
#   MANNY_CREDS        creds file override (default: relay's proxies.yaml chain)
#
# Subcommands:
#   start    launch the relay (idempotent — no-op if already up on this port)
#   stop     stop the relay for this port
#   status   report up/down + an egress IP check through the relay

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

PORT="${MANNY_SOCKS_PORT:-1080}"
# Empty default => socks_relay.py uses its own creds chain (proxies.yaml, then
# credentials.yaml). Set MANNY_CREDS to force a specific file.
CREDS="${MANNY_CREDS:-}"

PIDFILE="/tmp/manny_socks_relay_${PORT}.pid"
LOG="/tmp/manny_socks_relay_${PORT}.log"

# Prefer the repo venv python (has pyyaml); fall back to system python3.
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

cmd_start() {
  local pid
  if pid="$(relay_pid)"; then
    echo "relay already up on 127.0.0.1:${PORT} (pid=$pid) — no-op"
    return 0
  fi

  echo "starting SOCKS5 relay on 127.0.0.1:${PORT} -> dataimpulse (secret not shown) ..."
  : >"$LOG" 2>/dev/null || true
  # setsid + </dev/null + >log sever the tty so an ssh disconnect can't SIGHUP it.
  # socks_relay.py reads the upstream user/pass from the creds file ITSELF (never
  # argv/stdout/log) and forwards the dataimpulse session/geo token verbatim.
  # -u keeps its connection logging unbuffered. CREDS empty => relay's own chain.
  setsid "$PYBIN" -u "$SCRIPT_DIR/socks_relay.py" \
      --listen-host 127.0.0.1 --port "$PORT" ${CREDS:+--creds "$CREDS"} \
      >"$LOG" 2>&1 </dev/null &
  local relay_started=$!
  disown
  echo "$relay_started" >"$PIDFILE"

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
