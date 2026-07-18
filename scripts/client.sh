#!/usr/bin/env bash
# client.sh — manny RuneLite client lifecycle helper
#
# Encodes hard-won operational lessons from the refactor campaign
# (see journals/REFACTOR_CAMPAIGN_HANDOFF.md, "OPS LESSON" + "THERMAL POLICY"
# sections for the full history). Subcommands:
#
#   status              list running manny clients + thermal state
#   stop                kill ALL manny clients (cool-down / free-the-client)
#   start <account>     thermal-guarded safe launch of one account
#   restart <account>   stop then start
#
# DO NOT detect the client with `pgrep -f 'java -jar.*shaded.jar'` — that
# pattern self-matches THIS SCRIPT's own command line (it contains the string
# "java -jar ... shaded.jar" as an argv, e.g. inside `ps`/`pgrep` invocations
# spawned from here), so it finds itself and reports phantom/duplicate
# clients or kills the wrong thing. This bug wasted real debugging time
# during the campaign. Instead: `pgrep -x java` (exact comm match, immune to
# argv content) then confirm it's a manny client by reading
# MANNY_ACCOUNT_ID out of /proc/<pid>/environ.
#
# THERMAL POLICY: the client pins ~79% of a CPU core continuously (software
# rendering on Xvfb) and heat is the real cause of machine crashes, not
# software. Policy: client OFF unless a gate/test needs it; `start` refuses
# above 88C package temp and warns above 80C; every launch gets reniced to
# priority 15 immediately; always `stop` when done.

set -u

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNELITE_DIR="/home/wil/Desktop/runelite"
JAVA_BIN="/usr/lib/jvm/java-21-openjdk/bin/java"
[ -x "$JAVA_BIN" ] || JAVA_BIN="java"   # fallback if the pinned JDK moves

XVFB_DISPLAY=":2"
XVFB_SOCKET="/tmp/.X11-unix/X2"
XVFB_LOG="/tmp/xvfb2.log"

TEMP_REFUSE_C=88   # refuse to launch above this
TEMP_WARN_C=80      # warn but proceed above this

STOP_WAIT_SECS=8    # how long to wait after SIGTERM before SIGKILL fallback
LOGIN_WAIT_SECS=30  # how long to wait for LOGGED_IN after launch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

usage() {
  cat <<'EOF'
Usage: client.sh <status|stop|start|restart> [account]

  status              List running manny clients (pid/account/age) + thermal state.
  stop                Kill ALL manny clients (SIGTERM, then SIGKILL fallback).
  start <account>     Thermal-guarded launch of one account (kills existing first).
  restart <account>   stop, then start <account>.

Examples:
  scripts/client.sh status
  scripts/client.sh stop
  scripts/client.sh start new
  scripts/client.sh restart newbakshesh
EOF
}

# pkg_temp_c: prints package temperature in whole degrees C, or "n/a" if the
# x86_pkg_temp thermal zone can't be found/read. Never fails the script.
pkg_temp_c() {
  local zone type_file temp_file millideg
  for type_file in /sys/class/thermal/thermal_zone*/type; do
    [ -r "$type_file" ] || continue
    if [ "$(cat "$type_file" 2>/dev/null)" = "x86_pkg_temp" ]; then
      zone="$(dirname "$type_file")"
      temp_file="$zone/temp"
      if [ -r "$temp_file" ]; then
        millideg="$(cat "$temp_file" 2>/dev/null)"
        if [ -n "${millideg:-}" ] && [ "$millideg" -eq "$millideg" ] 2>/dev/null; then
          echo $(( millideg / 1000 ))
          return 0
        fi
      fi
    fi
  done
  echo "n/a"
  return 1
}

loadavg_str() {
  cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo "n/a"
}

# manny_client_pids: prints one "<pid> <account>" pair per line for every
# running manny client. Uses `pgrep -x java` (exact comm match) + a
# MANNY_ACCOUNT_ID check on /proc/<pid>/environ — see the header comment for
# why `pgrep -f 'java -jar.*shaded.jar'` is banned.
manny_client_pids() {
  local pid acct environ_file
  for pid in $(pgrep -x java 2>/dev/null); do
    environ_file="/proc/$pid/environ"
    [ -r "$environ_file" ] || continue
    acct="$(tr '\0' '\n' < "$environ_file" 2>/dev/null | sed -n 's/^MANNY_ACCOUNT_ID=//p')"
    [ -n "$acct" ] || continue
    echo "$pid $acct"
  done
}

# pid_age: prints elapsed wall-clock seconds for a pid (via ps etimes), or
# "?" if the pid has already vanished (race between listing and querying).
pid_age_secs() {
  local pid="$1"
  ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ' || true
}

human_age() {
  local secs="$1"
  if [ -z "$secs" ] || ! [ "$secs" -eq "$secs" ] 2>/dev/null; then
    echo "?"
    return
  fi
  if [ "$secs" -lt 60 ]; then
    echo "${secs}s"
  elif [ "$secs" -lt 3600 ]; then
    echo "$(( secs / 60 ))m$(( secs % 60 ))s"
  else
    echo "$(( secs / 3600 ))h$(( (secs % 3600) / 60 ))m"
  fi
}

# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
cmd_status() {
  echo "=== manny clients ==="
  local found=0 line pid acct age
  while IFS=' ' read -r pid acct; do
    [ -n "${pid:-}" ] || continue
    found=1
    age="$(pid_age_secs "$pid")"
    printf '  pid=%-8s account=%-16s age=%s\n' "$pid" "$acct" "$(human_age "$age")"
  done < <(manny_client_pids)
  if [ "$found" -eq 0 ]; then
    echo "  (none running)"
  fi

  echo
  echo "=== thermal / load ==="
  local temp
  temp="$(pkg_temp_c)"
  echo "  package temp: ${temp}C"
  echo "  loadavg (1/5/15m): $(loadavg_str)"
  if [ "$temp" != "n/a" ] 2>/dev/null; then
    if [ "$temp" -ge "$TEMP_REFUSE_C" ] 2>/dev/null; then
      echo "  WARNING: temp >= ${TEMP_REFUSE_C}C — let the machine cool, do not start a client"
    elif [ "$temp" -ge "$TEMP_WARN_C" ] 2>/dev/null; then
      echo "  NOTE: temp >= ${TEMP_WARN_C}C — elevated, watch it"
    fi
  fi
}

# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------
# stop_all_clients: kills every manny client found via manny_client_pids.
# SIGTERM first, waits up to STOP_WAIT_SECS polling for exit, then SIGKILL
# any stragglers. Prints what was killed. Safe to call with zero clients
# running (clean no-op). Used both by the `stop` subcommand and by `start`
# (which must clear any existing client before launching a new one — running
# two clients on the same account gets one JVM-killed by Jagex for duplicate
# login, which caused an unexplained crash previously).
stop_all_clients() {
  local pairs pid acct killed_any=0
  pairs="$(manny_client_pids)"

  if [ -z "$pairs" ]; then
    echo "no manny clients running (nothing to stop)"
    return 0
  fi

  echo "stopping manny clients:"
  echo "$pairs" | while IFS=' ' read -r pid acct; do
    [ -n "${pid:-}" ] || continue
    echo "  SIGTERM pid=$pid account=$acct"
    kill -TERM "$pid" 2>/dev/null || true
  done
  killed_any=1

  # Wait for graceful exit, polling manny_client_pids again (don't trust the
  # captured pid list — re-check by environ each time in case of races).
  local waited=0
  while [ "$waited" -lt "$STOP_WAIT_SECS" ]; do
    if [ -z "$(manny_client_pids)" ]; then
      break
    fi
    sleep 1
    waited=$(( waited + 1 ))
  done

  local stragglers
  stragglers="$(manny_client_pids)"
  if [ -n "$stragglers" ]; then
    echo "stragglers after ${STOP_WAIT_SECS}s, SIGKILL:"
    echo "$stragglers" | while IFS=' ' read -r pid acct; do
      [ -n "${pid:-}" ] || continue
      echo "  SIGKILL pid=$pid account=$acct"
      kill -KILL "$pid" 2>/dev/null || true
    done
    sleep 1
  fi

  if [ -z "$(manny_client_pids)" ]; then
    echo "all manny clients stopped"
    return 0
  else
    echo "WARNING: some manny clients still present after SIGKILL — check manually"
    return 1
  fi
}

cmd_stop() {
  stop_all_clients
}

# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------
ensure_xvfb() {
  if [ -e "$XVFB_SOCKET" ]; then
    echo "Xvfb $XVFB_DISPLAY already up"
    return 0
  fi
  echo "starting Xvfb $XVFB_DISPLAY ..."
  setsid Xvfb "$XVFB_DISPLAY" -screen 0 1600x1000x24 >"$XVFB_LOG" 2>&1 </dev/null &
  disown
  # give it a moment to create the socket
  local waited=0
  while [ ! -e "$XVFB_SOCKET" ] && [ "$waited" -lt 10 ]; do
    sleep 0.5
    waited=$(( waited + 1 ))
  done
  if [ -e "$XVFB_SOCKET" ]; then
    echo "Xvfb $XVFB_DISPLAY up"
    return 0
  else
    echo "ERROR: Xvfb $XVFB_DISPLAY did not come up, see $XVFB_LOG"
    return 1
  fi
}

cmd_start() {
  local acct="${1:-}"
  if [ -z "$acct" ]; then
    echo "ERROR: start requires an account, e.g.: client.sh start new" >&2
    return 1
  fi

  # 1. THERMAL GUARD
  local temp
  temp="$(pkg_temp_c)"
  if [ "$temp" != "n/a" ] 2>/dev/null; then
    if [ "$temp" -ge "$TEMP_REFUSE_C" ] 2>/dev/null; then
      echo "REFUSING to launch: package temp ${temp}C >= ${TEMP_REFUSE_C}C." >&2
      echo "Let the machine cool down (run 'client.sh stop' if a client is already up, then wait) before starting." >&2
      return 1
    elif [ "$temp" -ge "$TEMP_WARN_C" ] 2>/dev/null; then
      echo "WARNING: package temp ${temp}C >= ${TEMP_WARN_C}C — proceeding, but watch the heat."
    else
      echo "thermal ok: package temp ${temp}C"
    fi
  else
    echo "WARNING: could not read package temp (x86_pkg_temp not found) — proceeding without thermal guard"
  fi

  # 2. Kill any existing manny clients FIRST (duplicate-login JVM kill).
  echo "clearing any existing manny clients before launch..."
  stop_all_clients

  # 3. Ensure Xvfb :2 is up
  ensure_xvfb || return 1

  # 4. Pull creds via the venv — NEVER echo/print the tokens.
  local creds char_id sess_id
  creds="$(cd "$REPO_DIR" && ./venv/bin/python -c "
from mcptools.credentials import credential_manager
a = credential_manager.get_account('$acct')
if not a:
    raise SystemExit(1)
print(a['jx_character_id'], a['jx_session_id'])
" 2>/tmp/client_sh_creds_err.log)"
  local creds_rc=$?
  if [ "$creds_rc" -ne 0 ] || [ -z "$creds" ]; then
    echo "ERROR: failed to load credentials for account '$acct' (see /tmp/client_sh_creds_err.log)" >&2
    return 1
  fi
  char_id="$(echo "$creds" | cut -d' ' -f1)"
  sess_id="$(echo "$creds" | cut -d' ' -f2)"
  if [ -z "$char_id" ] || [ -z "$sess_id" ]; then
    echo "ERROR: empty jx_character_id/jx_session_id for account '$acct' — aborting" >&2
    return 1
  fi
  # creds/char_id/sess_id are intentionally never echoed/logged from here on.

  # 5. Launch with the exact recipe
  local jar
  jar="$(find "$RUNELITE_DIR/runelite-client/build/libs" -maxdepth 1 -iname '*shaded.jar' 2>/dev/null | head -1)"
  if [ -z "$jar" ]; then
    echo "ERROR: could not find shaded.jar under $RUNELITE_DIR/runelite-client/build/libs" >&2
    return 1
  fi

  local log
  if [ "$acct" = "new" ]; then
    log="/tmp/runelite.log"
  else
    log="/tmp/runelite_${acct}.log"
  fi
  : >"$log" 2>/dev/null || true

  echo "launching account='$acct' jar=$jar log=$log"
  DISPLAY="$XVFB_DISPLAY" \
    _JAVA_OPTIONS="-Xmx1536m -XX:MaxMetaspaceSize=192m" \
    MANNY_ACCOUNT_ID="$acct" \
    JX_CHARACTER_ID="$char_id" \
    JX_SESSION_ID="$sess_id" \
    setsid "$JAVA_BIN" -jar "$jar" >"$log" 2>&1 </dev/null &
  local java_pid=$!
  disown

  # unset the credential vars now that the process has them in its own environ
  unset creds char_id sess_id

  if ! kill -0 "$java_pid" 2>/dev/null; then
    echo "ERROR: client process (pid=$java_pid) died immediately, check $log" >&2
    tail -n 15 "$log" 2>/dev/null >&2 || true
    return 1
  fi
  echo "launched pid=$java_pid"

  # 6. THERMAL: lower its scheduling priority immediately.
  if renice 15 "$java_pid" >/dev/null 2>&1; then
    echo "reniced pid=$java_pid to priority 15"
  else
    echo "WARNING: renice failed for pid=$java_pid (non-fatal)"
  fi

  # 7. Wait up to LOGIN_WAIT_SECS for LOGGED_IN
  local t0 waited=0
  t0="$(date +%s)"
  while [ "$waited" -lt "$LOGIN_WAIT_SECS" ]; do
    if grep -q 'Game state is now LOGGED_IN' "$log" 2>/dev/null; then
      local elapsed=$(( $(date +%s) - t0 ))
      echo "READY: account='$acct' logged in in ${elapsed}s (pid=$java_pid)"
      echo
      echo "REMINDER: run 'scripts/client.sh stop' when the gate/test is done to cool the machine."
      return 0
    fi
    if ! kill -0 "$java_pid" 2>/dev/null; then
      echo "FAIL: client process died while waiting for login. Last log lines:" >&2
      tail -n 15 "$log" 2>/dev/null >&2 || true
      return 1
    fi
    sleep 1
    waited=$(( waited + 1 ))
  done

  echo "FAIL: did not see LOGGED_IN within ${LOGIN_WAIT_SECS}s. Last log lines:" >&2
  tail -n 15 "$log" 2>/dev/null >&2 || true
  return 1
}

# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------
cmd_restart() {
  local acct="${1:-}"
  if [ -z "$acct" ]; then
    echo "ERROR: restart requires an account, e.g.: client.sh restart new" >&2
    return 1
  fi
  cmd_stop
  cmd_start "$acct"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
  local sub="${1:-}"
  [ -n "$sub" ] && shift || true
  case "$sub" in
    status)  cmd_status "$@" ;;
    stop)    cmd_stop "$@" ;;
    start)   cmd_start "$@" ;;
    restart) cmd_restart "$@" ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    "")
      usage
      exit 1
      ;;
    *)
      echo "ERROR: unknown subcommand '$sub'" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
