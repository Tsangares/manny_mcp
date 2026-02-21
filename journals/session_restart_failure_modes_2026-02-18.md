# Session Restart Failure Modes - Lessons Learned
**Date:** 2026-02-18

## The Problem

After a system reboot, restarting RuneLite caused multiple cascading failures: gamescope only started one display instead of three, RuneLite window size changed from 796x577 to 1038x577, breaking all minimap navigation, and the disconnect screen couldn't be clicked to reconnect. What looked like a simple restart became a 30+ minute recovery.

## Root Cause

Multiple independent failure modes stacked on top of each other:
1. `start_gamescopes.sh` exits with code 1 if any display fails to start, even if some succeeded
2. RuneLite window width changes on restart if the sidebar state changed (796 → 1038px)
3. Minimap nav coordinates hardcoded to window dimensions - wrong size = all GOTO fails silently
4. Disconnect screen drawn by game renderer, not as widgets - find_widget/click_text can't find buttons
5. Plugin state file goes stale on disconnect but process stays alive - looks like freeze not disconnect

## Key Lessons

### 1. Always verify window size after restart

**What happened:** After reboot, RuneLite opened at 1038x577 instead of 796x577. All GOTO commands failed with "smartMinimapClick failed" because the minimap bounds were calculated from the wrong dimensions.

**Why:** RuneLite remembers its window state. If the sidebar was expanded when it last closed, it reopens expanded. The plugin's minimap coordinate math assumes 796x577.

**Solution:**
```python
# BAD - assume window is correct size
start_runelite(account_id="main", display=":2")
# immediately start routine - nav will silently fail

# GOOD - verify window size before running
DISPLAY=:2 xdotool getwindowgeometry <window_id>
# If not 796x577, stop_runelite() and start again
# Second start usually restores correct size
```

### 2. Check gamescope exit code ≠ check if displays are running

**What happened:** `./start_gamescopes.sh` exited with code 1 but `:2` was running. Only one of three displays started.

**Why:** The script exits 1 if any display fails, even if others succeed.

**Solution:**
```bash
# BAD - trust exit code
./start_gamescopes.sh && echo "all good"

# GOOD - check status explicitly
./start_gamescopes.sh
./start_gamescopes.sh status  # Check what actually started
```

### 3. Disconnect screen buttons are not widgets

**What happened:** After disconnect, "Try again" button appeared on screen but `find_widget("Try again")` returned 0 results. Clicking via `send_input` at various coordinates also failed.

**Why:** The OSRS disconnect/connection-lost screen is rendered directly by the game renderer, not through the RuneLite widget system. No widget IDs exist. Additionally, `send_input` coordinates are in Java AWT canvas space (765x503) which doesn't 1:1 map to what's visible in the screenshot.

**Solution:** Don't try to click through it - just restart RuneLite. The auto-login will handle reconnection cleanly.
```python
# BAD - waste time trying to click the button
find_widget("Try again")  # returns nothing
send_input(click, 382, 310)  # misses

# GOOD - just restart
stop_runelite(account_id="main")
start_runelite(account_id="main", display=":2")
# Plugin's auto-login handles the rest
```

### 4. Stale state file ≠ always frozen - could be disconnected

**What happened:** State file went stale (7+ minutes old). `check_health()` reported unhealthy. But the RuneLite process was still running and the plugin was still processing commands - it was just disconnected from the game server.

**Why:** The state file is updated every game tick (~600ms). During a disconnect, no game ticks fire, so the file goes stale even though the plugin thread is alive and healthy.

**Solution:** Screenshot first to diagnose before restarting:
```python
# BAD - immediately restart on stale state
if health["state_file"]["age_seconds"] > 30:
    stop_runelite()  # kills a healthy client that just needs reconnect

# GOOD - check what's actually on screen
get_screenshot()  # see if it's disconnect screen vs actual freeze
# If disconnect screen → try reconnect or restart
# If game still showing (loading screen etc) → wait longer
```

### 5. Starting routine mid-session requires correct --start-step

**What happened:** After a reboot with the player underground holding bars, starting the routine from step 1 failed because the F2P nav checker blocked the GOTO path (it passed through underground coordinates it flagged as P2P area).

**Why:** Step 1 GOTO target is Falador East Bank on the surface. The pathfinder computed a route that touched underground P2P tiles. When underground, the routine should start from step 11 (exit mine) not step 1.

**Solution:**
```python
# BAD - always restart from step 1
./run_routine.py superheat.yaml --loops 50

# GOOD - check current location first
state = get_game_state()
plane = state["player"]["location"]["plane"]  # actually always 0 even underground
# Check y coordinate: underground = y > 9000
if state["player"]["location"]["y"] > 9000:
    ./run_routine.py superheat.yaml --loops 50 --start-step 11
else:
    ./run_routine.py superheat.yaml --loops 50
```

### 6. Client thread freeze pattern

**What happened:** Client froze mid-session with "Client thread timeout after 5000ms - client thread may be blocked." State file went stale, inventory full of bars, player standing still.

**Why:** The Java client thread deadlocked (likely in a bank-open verification call at `GameEngine$GameHelpers.isBankOpen:3755`). This is distinct from a disconnection - the process is running but the game thread is blocked.

**Distinguishing freeze from disconnect:**
- **Disconnect:** State file stale, but screenshot shows disconnect screen, plugin responds to commands
- **Freeze:** State file stale, screenshot shows game normally, plugin does NOT respond to commands

```python
# Diagnose correctly before acting
health = check_health()
if health["state_file"]["age_seconds"] > 30:
    screenshot = get_screenshot()  # analyze what's visible
    response = get_command_response()  # did last command produce output?
    # if no response → frozen → restart
    # if disconnect screen visible → restart (faster than clicking)
```

## Anti-Patterns

1. **Don't** start the routine immediately after `start_runelite()` without verifying window size - nav will fail silently and the routine will keep "failing" steps with no obvious error
2. **Don't** try to click the OSRS disconnect screen via `send_input` coordinates - the canvas space doesn't match screenshot pixels reliably; just restart instead
3. **Don't** restart RuneLite on stale state file alone - screenshot first to distinguish disconnect vs freeze
4. **Don't** start from step 1 when the player is underground - use `--start-step 11` to exit the mine first

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `DISPLAY=:2 xdotool getwindowgeometry <id>` | Verify window is 796x577 not 1038x577 |
| `./start_gamescopes.sh status` | Verify which displays actually started |
| `get_screenshot()` | Distinguish disconnect screen from freeze |
| `get_command_response()` | Check if plugin thread is responsive |
| `check_health()` | State file age + process status |

## Interface Gaps Identified

- [ ] Plugin needs: `auto_reconnect` tool should work without requiring `runelite_manager.stop()` - currently errors with `'MultiRuneLiteManager' object has no attribute 'stop'`
- [ ] MCP needs: Window size verification step in `start_runelite()` or a separate check tool
- [ ] MCP needs: Better distinction between "client frozen" and "client disconnected" in `check_health()` output
- [ ] CLAUDE.md needs: Document that routine `--start-step` should be 11 when player is underground at session start
