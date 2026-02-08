# Superheat Steel Bar Automation Loop - Lessons Learned
**Date:** 2026-02-06

## The Problem

Automated superheat steel bar loop (mine 2 coal → mine 1 iron → superheat → repeat) had a 16% retry rate from false timeouts, a banking phase that silently failed on first attempt, and no crash detection — causing the script to spin through empty loops for 40+ minutes after a client freeze.

## Root Cause

Three independent issues compounded:

1. **Distance calculation mismatch** between GOTO (Chebyshev) and `location:X,Y` condition (Manhattan) in `mcptools/tools/monitoring.py:593-594`
2. **Bash log-tailing race** — `tail -n +$line_count` can miss lines when the log file grows between capturing line count and grepping
3. **BANK_WITHDRAW returns success before server processes** — `BankWithdrawCommand.java:326` explicitly skips inventory verification ("blocks client thread")

## Key Lessons

### 1. Manhattan vs Chebyshev Distance Causes Most GOTO Timeouts

**What happened:** `send_and_await("GOTO 3034 9738 0", "location:3034,9738")` timed out every single time at iron rocks, even though the player arrived successfully.

**Why:** GOTO uses Chebyshev distance (`max(dx, dy)`) with threshold 1. The Python `location:X,Y` condition uses Manhattan distance (`dx + dy`) with threshold 3. A player at (3035, 9735) relative to target (3034, 9738):
- Chebyshev: `max(1, 3) = 3` → passes threshold 3
- Manhattan: `1 + 3 = 4` → fails threshold 3

```python
# BAD (monitoring.py:593) — Manhattan, too strict on diagonals
distance = abs(current_x - target_x) + abs(current_y - target_y)
return distance <= 3

# GOOD — Chebyshev, matches GOTO's internal arrival logic
distance = max(abs(current_x - target_x), abs(current_y - target_y))
return distance <= 3
```

**Time wasted:** Every GOTO to iron rocks (step 10) timed out — 15s wasted per loop iteration, ~6 min wasted per 25-loop trip.

### 2. Fixed-Sleep Banking Fails Silently — Use State-Based Waits

**What happened:** First bash script version used `sleep 12` after GOTO to bank. Player hadn't arrived, so BANK_OPEN failed silently, DEPOSIT_ALL failed, withdrawals failed — script continued with empty inventory, looped through outer loops doing nothing.

**Why:** Walk time from Mining Guild ladder to Falador East Bank varies (10-18s depending on pathing). Fixed sleeps that work 80% of the time silently fail 20%.

```bash
# BAD — fixed sleeps, fails silently
send_cmd "GOTO 3012 3355 0"
sleep 12
send_cmd "BANK_OPEN"
sleep 2

# GOOD — coordinate polling with timeout
send_cmd "GOTO 3012 3355 0"
wait_near 3012 3355 25  # polls state file for dx≤5 && dy≤5
send_cmd "BANK_OPEN"
wait_for_log "BANK_OPEN.*Command succeeded" 15 "$lc"
```

**Time wasted:** First run's banking phase failed entirely. Script ran 11 fake outer loops before being stopped manually (~15 min wasted).

### 3. Stale State File Detection is Essential for Automation Scripts

**What happened:** Client froze (window went 1x1), state file stopped updating. Script kept running for 40+ minutes, hitting timeouts on every command, cycling through outer loops.

**Why:** State file at `/tmp/manny_main_state.json` is written every game tick (~600ms). If age > 60s, the plugin is frozen. The script had no health check.

```bash
# GOOD — check at start of every inner loop
check_stale() {
    local file_age=$(( $(date +%s) - $(stat -c %Y "$STATE_FILE") ))
    if [ "$file_age" -gt 60 ]; then
        echo "STATE FILE STALE (${file_age}s) - plugin frozen!"
        return 1
    fi
}
```

**Time wasted:** 40+ minutes of spinning before manual intervention.

### 4. BANK_WITHDRAW "Success" Doesn't Mean Item Was Withdrawn

**What happened:** `BANK_WITHDRAW Rune_pickaxe 1` logged "Command succeeded" but pickaxe wasn't in inventory after closing bank.

**Why:** `BankWithdrawCommand.java:326`:
```java
// Don't verify here - inventory check while bank is open blocks client thread
// Let the caller verify after appropriate delays
return true;  // Returns success after clicking, not after server processes
```

The command clicks the item and types the quantity, then returns `true`. Server-side withdrawal is async. If you close the bank too quickly, the withdrawal may not have processed.

```bash
# BAD — trust "Command succeeded" and move on
send_cmd "BANK_WITHDRAW Rune_pickaxe 1"
sleep 0.5
send_cmd "BANK_CLOSE"

# GOOD — wait for success log AND add buffer before next command
send_cmd "BANK_WITHDRAW Rune_pickaxe 1"
wait_for_log "BANK_WITHDRAW.*Command succeeded" 15 "$lc"
sleep 1  # Let server process the withdrawal
send_cmd "BANK_CLOSE"
```

### 5. MINE_ORE count Parameter Works Reliably — Use It

**What happened:** Original routine had two separate `MINE_ORE coal` steps. Step 10 had no await_condition, just `delay_after_ms: 500`.

**Why:** `MINE_ORE coal 2` handles the full cycle internally: finds rock → clicks → waits for ore → finds next rock → clicks → waits → returns. Logs: `[MINE_ORE] Completed - mined 2 coal ore(s) (target reached)`. Eliminates an entire step and its failure modes.

```yaml
# BAD — two separate steps, second has no await
- action: MINE_ORE
  args: "coal"
  await_condition: "has_item:Coal"
- action: MINE_ORE
  args: "coal"
  delay_after_ms: 500  # hopes 500ms is enough??

# GOOD — single command, blocks until done
- action: MINE_ORE
  args: "coal 2"
  timeout_ms: 60000
```

### 6. Ladder Transitions: Check Y-Coordinate, Not Location

**What happened:** `location:3019,3339` condition for surface arrival was unreliable (3-tile threshold edge case again). But y-coordinate is a binary signal: underground > 5000, surface < 5000.

```bash
# BAD — location condition with threshold issues
send_and_await("INTERACT_OBJECT Ladder Climb-up", "location:3019,3339")

# GOOD — binary y-coordinate check
send_cmd "INTERACT_OBJECT Ladder Climb-up"
for i in $(seq 1 15); do
    sleep 1
    py=$(jq -r '.player.location.y' "$STATE_FILE")
    if [ "$py" -lt 5000 ]; then
        echo "On surface (y=$py)"
        break
    fi
done
```

## Anti-Patterns

1. **Don't use fixed sleeps for GOTO** — Walk time varies. Use coordinate polling or `send_and_await` with location condition.
2. **Don't trust BANK_WITHDRAW "success"** — It means "clicked successfully", not "item withdrawn". Verify inventory or add delay.
3. **Don't run automation without staleness detection** — A frozen client wastes unbounded time. Check state file age every loop.
4. **Don't use `has_item:X` as await for MINE_ORE when ore already in inventory** — The condition is instantly true. Use `idle` or log-based detection for blocking commands.
5. **Don't rely on `location:X,Y` for exact arrival** — Chebyshev distance of 3 tiles is a wide area. For precision, poll coordinates directly.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail -50 /tmp/runelite_main.log` | Direct log access (MCP `get_logs` sometimes returns empty) |
| `stat -c %Y /tmp/manny_main_state.json` | Check state file freshness (>60s = frozen) |
| `jq '.player.inventory.used' /tmp/manny_main_state.json` | Quick inventory count |
| `jq '.player.location' /tmp/manny_main_state.json` | Quick position check |
| `grep "Command executed successfully" /tmp/runelite_main.log \| tail -5` | Verify recent commands actually ran |

## Interface Gaps Identified

- [ ] **Plugin needs:** Camera yaw/pitch in state file JSON (readable from `client.getCameraYaw()/getPitch()` but not exposed)
- [ ] **Plugin needs:** Zoom level in state file (NOT possible — RuneLite API has no getter, only setter via Robot mouse wheel)
- [ ] **MCP needs:** Chebyshev distance in `location:X,Y` condition (`monitoring.py:593`) to match GOTO arrival logic
- [ ] **MCP needs:** `BANK_WITHDRAW` inventory verification (or document that callers must verify)
- [ ] **YAML routine needs:** `CAMERA_STABILIZE` step to prevent zoom drift from MINE_ORE camera adjustments

## Files Modified

| File | Change |
|------|--------|
| `routines/skilling/superheat_steel_bars.yaml` | Consolidated coal mining (2 steps → 1), removed F6 key press, renumbered steps 9-14, updated loop config |
