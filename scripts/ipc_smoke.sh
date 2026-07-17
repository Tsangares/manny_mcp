#!/usr/bin/env bash
# ipc_smoke.sh — manny plugin IPC smoke test harness
#
# Exercises the file-IPC control loop against a live RuneLite+manny client.
# Used as the per-wave "smoke gate" during the refactor campaign.
#
# Usage: ./ipc_smoke.sh [account_id]   (default account_id = "new")
#
# Exit 0 = all checks pass. Non-zero = a check failed (prints which).
# Each check prints PASS/FAIL and timing. Designed to be re-run after every wave;
# baseline behavior (pre-refactor) is captured so regressions are visible.

set -uo pipefail
ACCT="${1:-new}"
SUF=""
[ "$ACCT" != "default" ] && SUF="_${ACCT}"
CMD="/tmp/manny${SUF}_command.txt"
RESP="/tmp/manny${SUF}_response.json"
STATE="/tmp/manny${SUF}_state.json"

PASS=0; FAIL=0
ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
now_ms() { date +%s%3N; }

rid() { printf '%08x' $(( (RANDOM<<16) ^ RANDOM ^ $(date +%N) & 0xffffffff )); }

# send <command-with-args> -> echoes the rid used; waits up to <timeout_ms> for a
# response whose request_id matches, printing round-trip latency.
send_await() {
  local cmdline="$1" timeout_ms="${2:-3000}"
  local r; r=$(rid)
  local before_mtime; before_mtime=$(stat -c %Y "$RESP" 2>/dev/null || echo 0)
  local t0; t0=$(now_ms)
  printf '%s --rid=%s' "$cmdline" "$r" > "$CMD"
  local deadline=$(( t0 + timeout_ms ))
  while [ "$(now_ms)" -lt "$deadline" ]; do
    if [ -f "$RESP" ]; then
      local got; got=$(python3 -c "import json,sys
try:
    d=json.load(open('$RESP'))
    print(d.get('request_id',''))
except Exception:
    print('')" 2>/dev/null)
      if [ "$got" = "$r" ]; then
        local t1; t1=$(now_ms)
        echo $(( t1 - t0 ))
        return 0
      fi
    fi
    sleep 0.02
  done
  echo "-1"
  return 1
}

echo "=== manny IPC smoke test (account=$ACCT) ==="
echo "  command=$CMD"
echo "  response=$RESP"
echo "  state=$STATE"
echo

# Check 0: client process alive
if pgrep -f 'java -jar.*shaded' >/dev/null || pgrep -f 'net.runelite.client' >/dev/null; then
  ok "client process running"
else
  bad "no RuneLite client process found"; echo; echo "RESULT: $PASS pass / $FAIL fail"; exit 1
fi

# Check 1: rid round-trip latency < 1500ms (post-Wave-1 target; pre-fix this is ~3000ms)
echo "[1] GET_GAME_STATE rid round-trip"
lat=$(send_await "GET_GAME_STATE" 4000)
if [ "$lat" -ge 0 ] 2>/dev/null; then
  if [ "$lat" -lt 1500 ]; then ok "round-trip ${lat}ms (<1500)"; else bad "round-trip ${lat}ms (>=1500, watchdog likely still inverted)"; fi
else
  bad "no rid-matched response within 4000ms (command may be going to wrong mailbox)"
fi

# Check 2: burst of 3 commands — all acknowledged (pre-fix: single-slot mailbox loses some)
echo "[2] burst of 3 PING commands — no loss"
acked=0
for i in 1 2 3; do
  l=$(send_await "PING" 3000)
  [ "$l" -ge 0 ] 2>/dev/null && acked=$((acked+1))
  sleep 0.05
done
if [ "$acked" -eq 3 ]; then ok "3/3 acknowledged"; else bad "$acked/3 acknowledged (mailbox loss)"; fi

# Check 3: STOP interrupts a long WAIT (pre-fix: KILL/STOP paths broken)
echo "[3] STOP interrupts WAIT 30000"
printf 'WAIT 30000 --rid=%s' "$(rid)" > "$CMD"
sleep 1
t0=$(now_ms)
stoplat=$(send_await "STOP" 5000)
if [ "$stoplat" -ge 0 ] 2>/dev/null && [ "$stoplat" -lt 5000 ]; then
  ok "STOP acknowledged in ${stoplat}ms while WAIT in-flight"
else
  bad "STOP did not interrupt WAIT (interrupt path broken)"
fi

# Check 4: read-only lane — QUERY during WAIT does NOT cancel it (post-Wave-2 target)
echo "[4] read-only lane: QUERY_INVENTORY during WAIT 10000 (Wave-2+; informational pre-Wave-2)"
printf 'WAIT 10000 --rid=%s' "$(rid)" > "$CMD"
sleep 0.8
qlat=$(send_await "QUERY_INVENTORY" 3000)
if [ "$qlat" -ge 0 ] 2>/dev/null; then
  echo "  INFO: QUERY answered in ${qlat}ms (non-preemption verified separately once read-only lane lands)"
else
  echo "  INFO: QUERY not answered (expected pre-Wave-2 — it gets preempted or preempts)"
fi
# clean up the lingering WAIT
printf 'KILL --rid=%s' "$(rid)" > "$CMD"; sleep 0.5

# Check 5: state file freshness after a tick-inducing action
echo "[5] state file freshness"
if [ -f "$STATE" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$STATE") ))
  if [ "$age" -lt 15 ]; then ok "state file age ${age}s (<15)"; else bad "state file stale (${age}s — exporter idle or logged out)"; fi
else
  bad "state file absent (plugin not exporting / not logged in)"
fi

echo
echo "RESULT: $PASS pass / $FAIL fail"
[ "$FAIL" -eq 0 ]
