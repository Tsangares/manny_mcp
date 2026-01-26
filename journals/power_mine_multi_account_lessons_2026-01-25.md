# POWER_MINE Multi-Account and Navigation Issues - Lessons Learned
**Date:** 2026-01-25

## The Problem

POWER_MINE commands would either not execute at all (MCP command dispatch issue) or get stuck in pathfinding loops where the bot clicks "Cancel" repeatedly instead of mining. Commands frequently stopped with "Interrupted" status requiring constant restarts.

## Root Cause

Three distinct issues:

1. **MCP `send_command` not writing to account-specific file** - The MCP was dispatching commands but they weren't appearing in `/tmp/manny_main_command.txt`. The command file for multi-account mode uses `manny_<account_id>_command.txt` pattern.

2. **Pathfinder minimap click calculates wrong position** - When a rock is 1-3 tiles away but the click lands on an invalid position, the menu shows "Cancel" instead of "Walk here" or "Mine". The bot then loops retrying the same failed approach.

3. **POWER_MINE loop doesn't recover from pathfinding failures** - After 10 retries on a single rock, it should skip to a different rock but instead the whole command fails.

## Key Lessons

### 1. Manual Command File Writing Works When MCP Fails

**What happened:** `send_command(account_id="main", command="POWER_MINE iron")` returned `dispatched: true` but the plugin never received it.
**Why:** The command file `/tmp/manny_main_command.txt` was never created by the MCP.
**Solution:**
```python
# BAD - MCP send_command may silently fail
send_command(account_id="main", command="POWER_MINE iron")
# Shows dispatched: true but command file doesn't exist

# GOOD - Direct file write as fallback
Bash("echo 'POWER_MINE iron' > /tmp/manny_main_command.txt")
# Verify: cat /tmp/manny_main_command.txt
```

### 2. Navigation "Cancel" Loop Indicates Position Calculation Bug

**What happened:** Bot stuck for 5+ minutes clicking Cancel at minimap coordinates (634, 73-80) while trying to reach a rock 1 tile away.
**Why:** Minimap click calculation produced coordinates outside the valid game area, causing menu to show only "Cancel".
**Solution:**
```python
# When you see repeated "Cancel" clicks in logs:
# 1. Stop the command
echo "STOP" > /tmp/manny_main_command.txt

# 2. Manually move player to better position
echo "GOTO 3039 9776 0" > /tmp/manny_main_command.txt

# 3. Restart mining from new position
echo "POWER_MINE iron" > /tmp/manny_main_command.txt
```

### 3. Check Logs for "Cancel" Pattern to Detect Stuck State

**What happened:** State file showed "Idle" but mining XP wasn't increasing.
**Why:** The command response still showed old "Interrupted" status, masking the real problem.
**Solution:**
```bash
# BAD - Checking game state alone
get_game_state(fields=["scenario"])  # Shows "Idle" even when stuck

# GOOD - Check logs for Cancel pattern
tail -30 /tmp/runelite_main.log | grep -E "Cancel|NAV"
# If you see repeated "Cancel" clicks, navigation is stuck
```

## Anti-Patterns

1. **Don't rely solely on MCP send_command** - Verify command file exists after dispatch
2. **Don't wait indefinitely for POWER_MINE** - Check logs every 60s for Cancel loops
3. **Don't restart from same position after pathfinding failure** - Move player first

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `cat /tmp/manny_main_command.txt` | Verify command file was written |
| `tail -30 /tmp/runelite_main.log \| grep Cancel` | Detect navigation stuck in Cancel loop |
| `tail -30 /tmp/runelite_main.log \| grep -E "MINING\|animation"` | Confirm mining is actually happening |
| `echo "STOP" > /tmp/manny_main_command.txt` | Force stop stuck command |

## Interface Gaps Identified

- [ ] MCP needs: Investigate why `send_command` fails silently for multi-account mode
- [ ] Plugin needs: Better recovery from minimap click failures (skip to different rock after 3 failures, not 10)
- [ ] Plugin needs: Detect "Cancel" loop pattern and auto-abort with error message
- [ ] CLAUDE.md needs: Document manual command file writing as fallback

## Symptoms Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| `dispatched: true` but no activity | Command file not written | `echo "CMD" > /tmp/manny_main_command.txt` |
| XP stuck, repeated "Cancel" in logs | Pathfinder stuck | STOP, GOTO new position, restart |
| Command shows "Interrupted" immediately | Previous interrupt flag not cleared | Restart RuneLite |
| State file >30s stale | Plugin frozen | `stop_runelite` then `start_runelite` |
