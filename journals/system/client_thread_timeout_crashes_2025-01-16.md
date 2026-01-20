# Client Thread Timeout Crashes - 2025-01-16

## Pattern Observed

Multiple crashes during Karamja harpoon fishing routine, all showing the same error pattern:

```
ERROR n.r.c.p.m.utility.ClientThreadHelper - [BLOCKING] readFromClient TIMEOUT after 5000ms!
```

## Root Cause

The RuneLite client thread becomes blocked/frozen, causing all plugin commands to fail with 5-second timeouts. The client thread is responsible for:
- Rendering the game
- Processing game ticks
- Handling UI events

When it gets stuck, all `readFromClient()` calls time out.

## Specific Errors from 2025-01-16 16:26-16:28

1. **Map loading error** (16:26:57) - Initial trigger
   - `readFromClientWithRetry FAILED after 3 retries`

2. **INTERACT_OBJECT failed** - Couldn't find deposit box due to thread timeout
   - `No TileObject 'Bank deposit box' found within 15 tiles`

3. **Cascading failures** - All subsequent commands timed out:
   - `BANK_DEPOSIT_ITEM Raw_swordfish` (multiple attempts)
   - `BANK_DEPOSIT_ITEM Raw_tuna` (multiple attempts)
   - `GOTO 3029 3217 0` (multiple attempts)

## Likely Triggers

1. **Map loading** - When loading new map regions (common when traveling between areas)
2. **Memory pressure** - RuneLite running with `-Xmx1536m` may hit limits
3. **Plugin contention** - Multiple manny threads competing for client thread access
4. **Rendering lag** - GPU/display issues on virtual display :2

## Mitigation Ideas

1. Add timeout detection and auto-restart in MCP tools
2. Reduce command frequency during area transitions
3. Add "client health check" before starting long routines
4. Consider increasing heap size if memory is the issue

## Fixes Applied (2026-01-16)

### 1. Smart Freeze Detection in `auto_reconnect`
**File:** `mcptools/tools/monitoring.py`

Added `freeze_threshold_seconds` parameter (default: 60s). If state file is older than threshold, the tool now:
- Diagnoses as `PLUGIN_FREEZE` vs network disconnect
- Skips click attempts entirely (clicking dialogs won't help a frozen plugin)
- Goes straight to restart
- Returns `diagnosis: "PLUGIN_FREEZE"` in response for clarity

**Before:** Would waste 60+ seconds clicking dialogs then timing out before restarting.
**After:** Detects freeze immediately and restarts within seconds.

### 2. New `restart_if_frozen` Tool
**File:** `mcptools/tools/monitoring.py`

Lightweight proactive health check + restart:
```python
restart_if_frozen(stale_threshold_seconds=30)
```

- Returns immediately if plugin is healthy
- Restarts and waits for reconnection if frozen
- Use before starting long routines to ensure plugin is responsive

### 3. Pre-flight Staleness Check in `send_and_await`
**File:** `mcptools/tools/commands.py`

Before sending command, checks if state file is >30s stale:
- Returns immediately with `diagnosis: "PLUGIN_FROZEN"` error
- Suggests using `restart_if_frozen()` or `auto_reconnect()` first
- Prevents cascading timeout failures from a frozen plugin

**Before:** Would send command, wait full timeout, fail, send another command, wait, fail...
**After:** Fails fast with actionable diagnosis.

### Usage Pattern for Robust Routines

```python
# Before starting a routine, ensure plugin is healthy
restart_if_frozen(stale_threshold_seconds=30)

# Now safe to run commands - they'll fail fast if plugin freezes mid-routine
send_and_await("INTERACT_NPC Cook Talk-to", "idle")
```

### Recovery Pattern When Freeze Detected

```python
# If send_and_await returns diagnosis="PLUGIN_FROZEN"
auto_reconnect()  # Will detect freeze and restart immediately
# Then retry the command
```

## Impact

- Routine interrupted mid-execution
- Fish in inventory may be lost if crash happens before deposit
- Requires manual restart

## Times Observed

- ~12:43 PST - Map loading error during GOTO
- ~16:26-16:28 PST - Multiple timeout errors during deposit phase
- ~17:22 PST - State file stale (448s), plugin frozen but process alive
  - Error: "Unable to ping session service" (network/disconnect)
  - Last known state: Karamja (2920, 3151), empty inventory
  - Process still running (PID 16650) but unresponsive
- ~22:49 PST - readFromClientWithRetry FAILED, client thread timeouts
  - INTERACT_NPC Captain_Tobias Travel failed after 3 attempts
  - GOTO failed with 5000ms timeout
  - State file 15886s stale
