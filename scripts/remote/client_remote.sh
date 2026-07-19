#!/usr/bin/env bash
# client_remote.sh — host-agnostic manny client launcher  [PROTOTYPE]
#
# This is a PARAMETERIZED port of scripts/client.sh. client.sh is the source of
# truth for the operational lessons encoded here (pgrep -x java + /proc environ
# account detection, thermal guard, renice-15, duplicate-login kill-first,
# login-wait loop, never-echo-creds). client.sh hardcodes RUNELITE_DIR / JAVA_BIN
# / XVFB_DISPLAY for the laptop; this file reads them from the environment so the
# SAME script runs on ANY host after `provision`. It is deployed to every host by
# the manny_mcp rsync and invoked over SSH by `mannyctl`.
#
# It DOES NOT modify or replace client.sh — on the laptop you can keep using
# client.sh directly. Phase-2 refactor goal (see REMOTE_CLIENT_ARCHITECTURE.md):
# make client.sh itself env-overridable and collapse this file into it so there
# is one launcher. Until that refactor lands, keep the two in sync by hand.
#
# Config comes from env (with client.sh's laptop values as defaults):
#   RUNELITE_LIBS   dir containing *-shaded.jar   (default: laptop path)
#   JAVA_BIN        path to java 21               (default: /usr/lib/jvm/java-21-openjdk/bin/java)
#   XVFB_DISPLAY    e.g. ":2"                     (default: ":2")
#   TEMP_REFUSE_C   refuse launch at/above (C)    (default: 88)
#   TEMP_WARN_C     warn at/above (C)             (default: 80)
#   REPO_DIR        manny_mcp repo (for venv creds) (default: script's ../..)
#   NAV_BACKEND     Stage-2 nav flag (-Dmanny.navBackend) (default: "shadow")
#   MANNY_PROXY     "1" => egress via local SOCKS5 relay  (default: unset = OFF)
#   MANNY_SOCKS_PORT loopback relay port; setting it also enables proxy (default: 1080 when on)
#
# Subcommands (account-scoped — lane-2 safe, multiple accounts coexist):
#   status [account]        host status; with an account, scope the client list
#   start <account>         launch; kills ONLY this account's prior client
#   restart <account>       stop this account's client, then start it
#   stop <account>          stop ONLY this account's client (siblings untouched)
#   stop --all              ESCAPE HATCH: sweep EVERY manny client on the host

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

RUNELITE_LIBS="${RUNELITE_LIBS:-/home/wil/Desktop/runelite/runelite-client/build/libs}"
JAVA_BIN="${JAVA_BIN:-/usr/lib/jvm/java-21-openjdk/bin/java}"
[ -x "$JAVA_BIN" ] || JAVA_BIN="java"

# NAV_BACKEND: Stage-2 navigation feature flag (JVM -Dmanny.navBackend). Default
# 'shadow' = legacy follower still drives, plus log-only graph comparison
# ([NAV-SHADOW]); zero behaviour change. 'legacy' disables; 'graph' cuts over.
NAV_BACKEND="${NAV_BACKEND:-shadow}"

XVFB_DISPLAY="${XVFB_DISPLAY:-:2}"
XVFB_SOCKET="/tmp/.X11-unix/X${XVFB_DISPLAY#:}"
XVFB_LOG="/tmp/xvfb${XVFB_DISPLAY#:}.log"

# PROXY (opt-in, default OFF — zero behaviour change when unset). Egress the
# JVM's TCP through a local pproxy SOCKS5 relay so the client's traffic (incl.
# the raw OSRS game socket) leaves via the dataimpulse residential exit instead
# of the host's home IP. Enabled when MANNY_SOCKS_PORT is set OR MANNY_PROXY=1.
# See scripts/remote/proxy_relay.sh + journals/2026-07-19_proxy_ip_wiring_plan.md.
MANNY_PROXY="${MANNY_PROXY:-}"
MANNY_SOCKS_PORT="${MANNY_SOCKS_PORT:-}"
PROXY_ENABLED=""
if [ -n "$MANNY_SOCKS_PORT" ] || [ "$MANNY_PROXY" = "1" ]; then
  PROXY_ENABLED=1
  MANNY_SOCKS_PORT="${MANNY_SOCKS_PORT:-1080}"
fi

TEMP_REFUSE_C="${TEMP_REFUSE_C:-88}"
TEMP_WARN_C="${TEMP_WARN_C:-80}"

STOP_WAIT_SECS=8
LOGIN_WAIT_SECS=30

usage() {
  cat <<'EOF'
Usage: client_remote.sh <status|stop|start|restart> [account]
  status  [account]   list clients (all, or just <account>)
  start   <account>   launch; stops only THIS account's prior client
  restart <account>   stop this account's client, then start it
  stop    <account>   stop only THIS account's client (leaves siblings running)
  stop    --all       ESCAPE HATCH: stop EVERY manny client on the host
  (paths taken from env: RUNELITE_LIBS, JAVA_BIN, XVFB_DISPLAY, TEMP_*)
EOF
}

# pkg_temp_c: whole-degree package temp, or "n/a". Tries the laptop's
# x86_pkg_temp thermal zone first (same as client.sh), then falls back to a
# coretemp "Package id" hwmon input (diort's iMac reports there, not via
# x86_pkg_temp). Never fails the script.
pkg_temp_c() {
  local type_file zone temp_file millideg
  for type_file in /sys/class/thermal/thermal_zone*/type; do
    [ -r "$type_file" ] || continue
    if [ "$(cat "$type_file" 2>/dev/null)" = "x86_pkg_temp" ]; then
      zone="$(dirname "$type_file")"; temp_file="$zone/temp"
      if [ -r "$temp_file" ]; then
        millideg="$(cat "$temp_file" 2>/dev/null)"
        if [ -n "${millideg:-}" ] && [ "$millideg" -eq "$millideg" ] 2>/dev/null; then
          echo $(( millideg / 1000 )); return 0
        fi
      fi
    fi
  done
  # Fallback: coretemp hwmon "Package id 0"
  local label_file input_file
  for label_file in /sys/class/hwmon/hwmon*/temp*_label; do
    [ -r "$label_file" ] || continue
    case "$(cat "$label_file" 2>/dev/null)" in
      Package*|"CPU Package")
        input_file="${label_file%_label}_input"
        if [ -r "$input_file" ]; then
          millideg="$(cat "$input_file" 2>/dev/null)"
          if [ -n "${millideg:-}" ] && [ "$millideg" -eq "$millideg" ] 2>/dev/null; then
            echo $(( millideg / 1000 )); return 0
          fi
        fi
        ;;
    esac
  done
  echo "n/a"; return 1
}

loadavg_str() { cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo "n/a"; }

# manny_client_pids [account]: "<pid> <account>" per running client. pgrep -x
# java (exact comm, immune to argv self-match) + MANNY_ACCOUNT_ID from
# /proc/<pid>/environ. With an <account> arg, emit ONLY that account's clients
# (lane-2: sibling accounts must never appear in a scoped stop/status). The
# environ MANNY_ACCOUNT_ID is authoritative — it's exactly what cmd_start sets.
manny_client_pids() {
  local filter="${1:-}"
  local pid acct environ_file
  for pid in $(pgrep -x java 2>/dev/null); do
    environ_file="/proc/$pid/environ"
    [ -r "$environ_file" ] || continue
    acct="$(tr '\0' '\n' < "$environ_file" 2>/dev/null | sed -n 's/^MANNY_ACCOUNT_ID=//p')"
    [ -n "$acct" ] || continue
    [ -n "$filter" ] && [ "$acct" != "$filter" ] && continue
    echo "$pid $acct"
  done
}

cmd_status() {
  local filter="${1:-}" scope
  [ -n "$filter" ] && scope="account=$filter" || scope="all accounts"
  echo "=== manny clients ($XVFB_DISPLAY, $scope) ==="
  local found=0 pid acct
  while IFS=' ' read -r pid acct; do
    [ -n "${pid:-}" ] || continue
    found=1
    printf '  pid=%-8s account=%-16s\n' "$pid" "$acct"
  done < <(manny_client_pids "$filter")
  [ "$found" -eq 0 ] && echo "  (none running)"
  echo
  echo "=== thermal / load ==="
  local temp; temp="$(pkg_temp_c)"
  echo "  package temp: ${temp}C  (refuse>=${TEMP_REFUSE_C}, warn>=${TEMP_WARN_C})"
  echo "  loadavg (1/5/15m): $(loadavg_str)"
  if [ "$temp" != "n/a" ] 2>/dev/null; then
    if   [ "$temp" -ge "$TEMP_REFUSE_C" ] 2>/dev/null; then echo "  WARNING: temp >= refuse threshold — do not start a client"
    elif [ "$temp" -ge "$TEMP_WARN_C"   ] 2>/dev/null; then echo "  NOTE: elevated temp — watch it"; fi
  fi
}

# stop_clients [account] — SIGTERM, wait, then SIGKILL stragglers. With an
# <account> it stops ONLY that account's clients and leaves every sibling
# running (this is the lane-2 invariant: starting/stopping blast must never
# touch newbakshesh). An EMPTY account means the old blanket sweep — reachable
# only via the explicit `stop --all` escape hatch, never a default.
stop_clients() {
  local filter="${1:-}" scope
  [ -n "$filter" ] && scope="account=$filter" || scope="ALL accounts"
  local pairs pid acct; pairs="$(manny_client_pids "$filter")"
  if [ -z "$pairs" ]; then echo "no manny clients running for $scope (nothing to stop)"; return 0; fi
  echo "stopping manny clients ($scope):"
  echo "$pairs" | while IFS=' ' read -r pid acct; do
    [ -n "${pid:-}" ] || continue
    echo "  SIGTERM pid=$pid account=$acct"; kill -TERM "$pid" 2>/dev/null || true
  done
  local waited=0
  while [ "$waited" -lt "$STOP_WAIT_SECS" ]; do
    [ -z "$(manny_client_pids "$filter")" ] && break
    sleep 1; waited=$(( waited + 1 ))
  done
  local stragglers; stragglers="$(manny_client_pids "$filter")"
  if [ -n "$stragglers" ]; then
    echo "stragglers after ${STOP_WAIT_SECS}s, SIGKILL:"
    echo "$stragglers" | while IFS=' ' read -r pid acct; do
      [ -n "${pid:-}" ] || continue
      echo "  SIGKILL pid=$pid account=$acct"; kill -KILL "$pid" 2>/dev/null || true
    done
    sleep 1
  fi
  if [ -z "$(manny_client_pids "$filter")" ]; then echo "manny clients stopped ($scope)"; return 0
  else echo "WARNING: clients still present after SIGKILL — check manually"; return 1; fi
}

# stop_all_clients — explicit blanket sweep (the escape hatch). Kept as a named
# alias so the intent reads clearly at call sites.
stop_all_clients() { stop_clients ""; }

# cmd_stop [account|--all] — account-scoped by default; --all sweeps everything.
# Bare `stop` (no arg) is a deliberate error so a fat-fingered stop can never
# nuke a sibling account's live grind.
cmd_stop() {
  local arg="${1:-}"
  case "$arg" in
    --all|-a) stop_clients "" ;;
    "")       echo "ERROR: stop requires an account (or 'stop --all' to sweep every client)" >&2; return 1 ;;
    *)        stop_clients "$arg" ;;
  esac
}

ensure_xvfb() {
  if [ -e "$XVFB_SOCKET" ]; then echo "Xvfb $XVFB_DISPLAY already up"; return 0; fi
  echo "starting Xvfb $XVFB_DISPLAY ..."
  setsid Xvfb "$XVFB_DISPLAY" -screen 0 1600x1000x24 >"$XVFB_LOG" 2>&1 </dev/null &
  disown
  local waited=0
  while [ ! -e "$XVFB_SOCKET" ] && [ "$waited" -lt 10 ]; do sleep 0.5; waited=$(( waited + 1 )); done
  if [ -e "$XVFB_SOCKET" ]; then echo "Xvfb $XVFB_DISPLAY up"; return 0
  else echo "ERROR: Xvfb $XVFB_DISPLAY did not come up, see $XVFB_LOG"; return 1; fi
}

cmd_start() {
  local acct="${1:-}"
  [ -n "$acct" ] || { echo "ERROR: start requires an account" >&2; return 1; }

  # 1. THERMAL GUARD
  local temp; temp="$(pkg_temp_c)"
  if [ "$temp" != "n/a" ] 2>/dev/null; then
    if [ "$temp" -ge "$TEMP_REFUSE_C" ] 2>/dev/null; then
      echo "REFUSING to launch: package temp ${temp}C >= ${TEMP_REFUSE_C}C. Let it cool." >&2; return 1
    elif [ "$temp" -ge "$TEMP_WARN_C" ] 2>/dev/null; then
      echo "WARNING: package temp ${temp}C >= ${TEMP_WARN_C}C — proceeding, watch the heat."
    else echo "thermal ok: package temp ${temp}C"; fi
  else echo "WARNING: could not read package temp — proceeding without thermal guard"; fi

  # 2. Kill THIS account's existing client first (duplicate-login / crash-restart
  #    JVM kill). Scoped to $acct so a sibling account's client keeps running
  #    (lane-2). The old blanket sweep is gone from the start path on purpose.
  echo "clearing any existing '$acct' client before launch..."
  stop_clients "$acct"

  # 3. Xvfb
  ensure_xvfb || return 1

  # 4. Creds via the host venv — NEVER echo the tokens.
  local creds char_id sess_id creds_rc
  creds="$(cd "$REPO_DIR" && ./venv/bin/python -c "
from mcptools.credentials import credential_manager
a = credential_manager.get_account('$acct')
if not a: raise SystemExit(1)
print(a['jx_character_id'], a['jx_session_id'])
" 2>/tmp/client_remote_creds_err.log)"
  creds_rc=$?
  if [ "$creds_rc" -ne 0 ] || [ -z "$creds" ]; then
    echo "ERROR: failed to load credentials for '$acct' (see /tmp/client_remote_creds_err.log)." >&2
    echo "       Did you push creds to this host? (mannyctl <host> push-creds)" >&2
    return 1
  fi
  char_id="$(echo "$creds" | cut -d' ' -f1)"; sess_id="$(echo "$creds" | cut -d' ' -f2)"
  [ -n "$char_id" ] && [ -n "$sess_id" ] || { echo "ERROR: empty jx ids for '$acct'" >&2; return 1; }

  # 4b. PROXY (opt-in). If enabled, ensure the local SOCKS5 relay is up BEFORE
  #     launch and prepare the JVM socks props. On relay failure we ABORT the
  #     launch rather than fall back to direct egress — a proxied launch must
  #     never silently leak the home IP.
  local socks_props=""
  if [ -n "$PROXY_ENABLED" ]; then
    echo "proxy: ensuring SOCKS5 relay on 127.0.0.1:${MANNY_SOCKS_PORT} before launch ..."
    # Forward the port-per-lane upstream port + opt-in game-443 rewrite to the
    # relay (unset => default lane / no rewrite, unchanged behavior).
    if ! MANNY_SOCKS_PORT="$MANNY_SOCKS_PORT" \
         MANNY_UPSTREAM_PORT="${MANNY_UPSTREAM_PORT:-}" \
         MANNY_GAME_443="${MANNY_GAME_443:-}" \
         REPO_DIR="$REPO_DIR" "$SCRIPT_DIR/proxy_relay.sh" start; then
      echo "ERROR: proxy relay failed to start — refusing to launch (would leak home IP)." >&2
      return 1
    fi
    socks_props="-DsocksProxyHost=127.0.0.1 -DsocksProxyPort=${MANNY_SOCKS_PORT}"
  fi

  # 5. Launch
  local jar; jar="$(find "$RUNELITE_LIBS" -maxdepth 1 -iname '*shaded.jar' 2>/dev/null | head -1)"
  [ -n "$jar" ] || { echo "ERROR: no *shaded.jar under $RUNELITE_LIBS" >&2; return 1; }
  local log; [ "$acct" = "new" ] && log="/tmp/runelite.log" || log="/tmp/runelite_${acct}.log"
  : >"$log" 2>/dev/null || true
  echo "launching account='$acct' jar=$jar display=$XVFB_DISPLAY log=$log navBackend=$NAV_BACKEND${socks_props:+ socks=127.0.0.1:${MANNY_SOCKS_PORT}}"
  # $socks_props is intentionally UNQUOTED: it expands to two JVM -D args when the
  # proxy is enabled, or to nothing at all when it is not (default OFF path).
  DISPLAY="$XVFB_DISPLAY" \
    _JAVA_OPTIONS="-Xmx1536m -XX:MaxMetaspaceSize=192m" \
    MANNY_ACCOUNT_ID="$acct" \
    JX_CHARACTER_ID="$char_id" \
    JX_SESSION_ID="$sess_id" \
    setsid "$JAVA_BIN" -Dmanny.navBackend="$NAV_BACKEND" $socks_props -jar "$jar" >"$log" 2>&1 </dev/null &
  local java_pid=$!; disown
  unset creds char_id sess_id

  if ! kill -0 "$java_pid" 2>/dev/null; then
    echo "ERROR: client (pid=$java_pid) died immediately, check $log" >&2
    tail -n 15 "$log" 2>/dev/null >&2 || true; return 1
  fi
  echo "launched pid=$java_pid"

  # 6. renice
  if renice 15 "$java_pid" >/dev/null 2>&1; then echo "reniced pid=$java_pid to 15"
  else echo "WARNING: renice failed for pid=$java_pid (non-fatal)"; fi

  # 7. Wait for LOGGED_IN
  local t0 waited=0; t0="$(date +%s)"
  while [ "$waited" -lt "$LOGIN_WAIT_SECS" ]; do
    if grep -q 'Game state is now LOGGED_IN' "$log" 2>/dev/null; then
      echo "READY: '$acct' logged in in $(( $(date +%s) - t0 ))s (pid=$java_pid)"
      echo "REMINDER: 'client_remote.sh stop' when the gate/test is done."
      return 0
    fi
    if ! kill -0 "$java_pid" 2>/dev/null; then
      echo "FAIL: client died while waiting for login. Last log lines:" >&2
      tail -n 15 "$log" 2>/dev/null >&2 || true; return 1
    fi
    sleep 1; waited=$(( waited + 1 ))
  done
  echo "FAIL: no LOGGED_IN within ${LOGIN_WAIT_SECS}s. Last log lines:" >&2
  tail -n 15 "$log" 2>/dev/null >&2 || true; return 1
}

cmd_restart() { local acct="${1:-}"; [ -n "$acct" ] || { echo "ERROR: restart requires an account" >&2; return 1; }; stop_clients "$acct"; cmd_start "$acct"; }

main() {
  local sub="${1:-}"; [ -n "$sub" ] && shift || true
  case "$sub" in
    status)  cmd_status "$@" ;;
    stop)    cmd_stop "$@" ;;
    start)   cmd_start "$@" ;;
    restart) cmd_restart "$@" ;;
    -h|--help|help) usage; exit 0 ;;
    "") usage; exit 1 ;;
    *) echo "ERROR: unknown subcommand '$sub'" >&2; usage; exit 1 ;;
  esac
}
main "$@"
