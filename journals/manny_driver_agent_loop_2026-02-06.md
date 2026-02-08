# Manny Driver Agent Loop - Lessons Learned
**Date:** 2026-02-06

## The Problem

Building a standalone CLI agent (`manny_driver/`) that uses Gemini Flash to autonomously control OSRS via MCP. Multiple iterations were needed before achieving stable 30+ minute autonomous chicken farming sessions.

## Root Cause

Several interacting bugs in the agent loop, monitoring mode, and system prompt made the first ~6 iterations fail within minutes. The fundamental tension: Gemini Flash doesn't follow nuanced instructions well, so the system prompt and code guardrails must be very explicit.

## Key Lessons

### 1. Provider Auto-Detection Must Default to `"auto"`

**What happened:** `DriverConfig` defaulted to `provider: str = "anthropic"`. The `detect_provider()` function was only called when `provider == "auto"`, so it was never invoked.
**Why:** Claude Code's environment sets `ANTHROPIC_API_KEY` but subprocesses can't use it. Gemini was available but never auto-detected.
**Solution:**
```python
# BAD - detect_provider() never called
provider: str = "anthropic"

# GOOD - auto-detection runs, checks Gemini first
provider: str = "auto"
```

### 2. Gemini Flash Ignores Implicit Combat Instructions

**What happened:** System prompt said "Use KILL_LOOP for combat" as one bullet among many. Gemini ignored it and used `INTERACT_NPC Chicken Attack` repeatedly (doesn't loop).
**Why:** Gemini Flash needs prominent, repeated, explicit instructions. A buried bullet point isn't enough.
**Solution:** Added a dedicated `## COMBAT: USE KILL_LOOP (MANDATORY)` section with code examples of WRONG vs RIGHT, placed before all other rules. After this change, Gemini correctly used KILL_LOOP 100% of the time.

### 3. `run_directive()` Finally Block Kills Monitoring

**What happened:** `run_directive()` sets `self._running = False` in its `finally` block. When monitoring calls `run_directive()` for an intervention, it sets `_running=False` and the monitoring `while self._running` loop exits.
**Why:** `_running` is shared state between run_directive and run_monitoring with conflicting semantics.
**Solution:**
```python
# In the monitoring intervention block, after run_directive returns:
finally:
    self.config.max_tool_calls_per_turn = saved_max
    # run_directive sets _running=False in its finally block,
    # but we need monitoring to continue
    self._running = True
```

### 4. `goal_mode` Gated Monitoring on `tool_calls > 0`

**What happened:** When the LLM correctly obeyed "say monitoring and stop" (0 tool calls), `goal_mode` skipped monitoring because `if tool_calls > 0` was false.
**Why:** The gate was designed to skip monitoring when the LLM had nothing to do, but it also blocked the case where the LLM intentionally did nothing.
**Solution:** Changed to `if monitor_after:` (unconditional).

### 5. send_command File Overwriting

**What happened:** LLM returned 5 tool calls including 3 DROP_ITEM commands. Only the last one executed.
**Why:** `send_command` writes to `/tmp/manny_<account>_command.txt`. The plugin reads this file once per game tick (~600ms). Multiple writes between ticks means only the last one is seen.
**Solution:** Added 700ms delay between consecutive send_command/send_and_await calls in agent.py.

### 6. Monitoring Interventions Need Tool Call Limits

**What happened:** Monitoring triggered idle detection, called `run_directive()` with 20 max tool calls. Model used all 20 fighting manually. This repeated 10 times = 200 total tool calls of wasted effort.
**Why:** Monitoring interventions should be surgical (1-2 commands) not full agent sessions.
**Solution:** Cap monitoring interventions at 5 tool calls and tell the LLM explicitly: "Handle with 1-2 commands, then STOP."

### 7. `kill_command` is Destructive

**What happened:** Model called `kill_command` to "reset" before trying its own approach. This killed the running KILL_LOOP.
**Why:** Model treated it as a harmless "clear state" action.
**Solution:** Added to system prompt: "NEVER call kill_command unless explicitly told to stop an activity."

### 8. `is_alive` Returns False for Active Clients

**What happened:** Monitoring used `is_alive` as a health check. It returned false for the monkey account, triggering recovery every cycle.
**Why:** `is_alive` checks process state in a way that doesn't work for all account configurations.
**Solution:** Replaced `is_alive` with `get_game_state(fields=["location"])` as the health check in monitoring.

## Anti-Patterns

1. **Don't** let the LLM observe-loop (call get_game_state repeatedly without action) - Add observation loop detection to stuck_detector
2. **Don't** use `is_alive` in monitoring - Use `get_game_state` instead
3. **Don't** rely on `get_logs` for debugging in multi-account setups - It returns empty; check XP/inventory changes instead
4. **Don't** allow unlimited tool calls in monitoring interventions - Cap at 5 to prevent runaway loops
5. **Don't** share `_running` state between run_directive and run_monitoring without restoring it

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail /tmp/manny_driver_stdout.log` | See driver monitoring output and LLM actions |
| `tail /tmp/manny_driver_stderr.log` | See driver errors |
| `get_game_state(fields=["skills"])` | Verify XP progress directly |
| `tail /tmp/runelite_<account>.log` | Fallback when `get_logs` returns empty |

## Interface Gaps Identified

- [x] `get_logs` returns empty for account-specific instances (known issue, workaround: tail log file)
- [x] `is_alive` unreliable for multi-account (workaround: use get_game_state)
- [ ] No way to detect KILL_LOOP state (running/stopped) without checking XP trends
- [ ] No monitoring event hook system - interventions are poll-based only

## Files Modified

| File | Change |
|------|--------|
| `manny_driver/config.py` | Default provider `"auto"`, Gemini-first detection |
| `manny_driver/agent.py` | Command delays, monitoring `_running` fix, intervention limits, XP idle detection |
| `manny_driver/stuck_detector.py` | Observation loop detection (consecutive_observations counter) |
| `manny_driver/context.py` | Prominent KILL_LOOP section, command reference, system prompt overhaul |
| `manny_driver/__main__.py` | Removed `tool_calls > 0` gate for monitoring entry |

## What Finally Worked

The successful pattern for autonomous chicken farming:
1. Start KILL_LOOP externally via `send_command("KILL_LOOP Chicken none")`
2. Launch driver with directive "Say 'Monitoring' and stop. Do NOT call any tools."
3. Model enters monitoring mode with 0 tool calls
4. Monitoring polls every 30s, reports XP progress
5. If XP stalls for 90s, intervention fires with 5-tool-call limit
6. Model correctly uses `send_command("KILL_LOOP Chicken none")` to restart
7. Monitoring resumes after `_running` is restored

Result: 30+ minute stable sessions with automatic recovery, leveling Attack 6→11, Hitpoints 10→12, Prayer 2→5.
