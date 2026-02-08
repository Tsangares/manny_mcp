# Autonomous Combat Training - Architecture That Worked
**Date:** 2026-02-06

## What Happened

Trained the `monkey` account from fresh-off-Tutorial-Island (all level 1) to Attack 15, Strength 17, Defence 15, Hitpoints 18, Prayer 15 - entirely autonomously over ~2 hours of chicken farming at Lumbridge. The system ran with zero manual gameplay intervention.

## Architecture: 3-Layer Autonomy

The key insight is that different layers handle different timescales:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Claude Opus (strategic, minutes-scale)     │
│  - Switch combat styles between training phases      │
│  - Start/stop KILL_LOOP and manny-driver             │
│  - Monitor macro progress (XP milestones)            │
├─────────────────────────────────────────────────────┤
│  Layer 2: Gemini Flash via manny-driver (30s polls)  │
│  - Monitor game state every 30 seconds               │
│  - Handle inventory full (BURY_ALL, DROP_ALL)        │
│  - Restart KILL_LOOP when XP stalls for 90s          │
│  - Cost: ~$0.02 for the entire 2-hour session        │
├─────────────────────────────────────────────────────┤
│  Layer 3: Manny Plugin KILL_LOOP (tick-level, 600ms) │
│  - Find nearest chicken, attack, wait for kill       │
│  - Loot drops, bury bones automatically              │
│  - Repeat indefinitely until stopped                 │
│  - Cost: Free (runs on Java plugin side)             │
└─────────────────────────────────────────────────────┘
```

### Why This Split Works

- **KILL_LOOP** handles the fast loop (find target, attack, loot) at game-tick speed. An LLM would be far too slow and expensive for this.
- **Gemini Flash** handles the medium loop (is inventory full? did KILL_LOOP stop?). It's cheap enough to poll every 30s and smart enough to call `BURY_ALL` or `KILL_LOOP Chicken none` when needed.
- **Claude Opus** handles the slow loop (have we hit the XP milestone? time to switch combat style?). It only acts every 15-60 minutes.

### Cost Breakdown

| Layer | Model | Cost for 2hr Session |
|-------|-------|---------------------|
| Strategic | Claude Opus 4.6 | Part of Claude Code session |
| Monitoring | Gemini 2.0 Flash | ~$0.02 (mostly idle polling) |
| Combat | Java plugin | Free |

Gemini Flash was called ~240 times for monitoring (every 30s for 2hr) but most calls were just "check state, report status, no action needed." It only invoked the LLM for actual interventions maybe 10-15 times total.

## What Gemini Flash Did Well

1. **Following explicit instructions**: After making the KILL_LOOP section prominent in the system prompt, Flash correctly used `send_command("KILL_LOOP Chicken none")` 100% of the time for restarts.
2. **Inventory management**: When the inventory full trigger fired, Flash checked inventory, identified bones and eggs, called `BURY_ALL` then `DROP_ALL Egg`. Smart prioritization without being told.
3. **Staying minimal**: With the 5-tool-call limit on interventions, Flash did what was needed in 1-3 calls and stopped. No over-observing.

## What Gemini Flash Did Poorly (Before Fixes)

1. **Ignoring buried instructions**: Originally used `INTERACT_NPC Chicken Attack` instead of `KILL_LOOP` because the KILL_LOOP instruction was just one bullet point among many.
2. **Calling kill_command to "reset"**: Destroyed the running KILL_LOOP trying to start fresh.
3. **Observation loops**: Called `get_game_state` 20+ times in a row without taking action.

All three were fixed by making the system prompt extremely explicit and adding code guardrails (observation loop detection, intervention tool-call limits).

## Key Patterns That Worked

### Pattern 1: "Say X and stop" Directive
```bash
python -m manny_driver --account monkey --max-tools 10 \
  "KILL_LOOP is already running. Say 'Monitoring' and stop. Do NOT call any tools."
```
This gets Flash into monitoring mode with 0-1 tool calls instead of letting it take over gameplay.

### Pattern 2: External KILL_LOOP + Driver Monitoring
Start KILL_LOOP externally (via MCP send_command), then launch the driver purely for monitoring. The LLM never needs to "figure out" how to fight - it just watches and restarts when needed.

### Pattern 3: Combat Style Switching Between Phases
```python
send_command("STOP")           # Stop KILL_LOOP
sleep(2)                       # Wait for it to stop
send_command("SWITCH_COMBAT_STYLE block")  # Change style
sleep(3)                       # Wait for click
send_command("KILL_LOOP Chicken none")     # Restart with new style
```
Important: STOP first, then switch, then restart. Switching while KILL_LOOP is running doesn't stick.

### Pattern 4: XP-Based Idle Detection
Monitor total XP across all skills. If unchanged for 3 consecutive 30s checks (~90s), KILL_LOOP has stopped. This catches all failure modes: character wandered off, KILL_LOOP errored, no targets available.

## Monitoring Interventions That Fired

| Trigger | Times | LLM Response |
|---------|-------|-------------|
| Inventory full (27-28/28) | ~4 | BURY_ALL + DROP_ALL Egg |
| XP idle (90s no gain) | ~3 | send_command("KILL_LOOP Chicken none") |
| Health critical | 0 | N/A (chickens are weak) |

## Final Stats

| Skill | Before | After |
|-------|--------|-------|
| Attack | 1 | **15** |
| Strength | 1 | **17** (overshot due to style switch timing) |
| Defence | 1 | **15** |
| Hitpoints | 10 | **18** |
| Prayer | 1 | **15** (free from auto-burying bones) |

## What Could Be Better

1. **Monitoring display hardcodes `atk_xp`** - Should show the currently training skill's XP
2. **No automatic combat style switching** - Had to manually switch between Att/Str/Def phases. Could add a training plan config.
3. **SWITCH_COMBAT_STYLE doesn't stick if sent while KILL_LOOP is running** - Need to STOP first, which wastes ~5s.
4. **Inventory fills slowly with eggs** - Could add an auto-drop rule for low-value items to the monitoring triggers.
