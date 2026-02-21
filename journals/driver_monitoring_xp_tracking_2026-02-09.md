# Driver Monitoring: XP Tracking & Multi-Skill Combat
**Date:** 2026-02-09

## The Problem

When training a non-Attack combat skill (Strength via "lunge", Defence via "block"), the monitoring status line showed `atk_xp=8408` which never changed. This made it look like the bot was idle, and was misleading when checking progress. Additionally, the monitoring's xp_idle detection seemed like it would break - but it turned out to be correct.

## What Actually Happened

### 1. xp_idle tracks TOTAL XP (already correct)

The `_check_monitoring_triggers` in `agent.py` already uses:
```python
current_xp = sum(s.get("xp", 0) for s in skills.values() if isinstance(s, dict))
```

This sums ALL skills, not just Attack. So when Strength XP goes up, total XP goes up, and xp_idle doesn't false-trigger. The xp_idle that fired was a genuine idle gap during combat style transition.

**Lesson:** Read the code before assuming it's broken.

### 2. Status line was misleading (fixed)

The monitoring status line was hardcoded to show `atk_xp`:
```python
atk = skills.get("attack", {})
f"atk_xp={atk.get('xp','?')}"
```

**Fixed to show combat levels compactly:**
```python
f"cmb={atk_lvl}/{str_lvl}/{def_lvl}"
```

Now shows `cmb=25/10/1` (A/S/D levels) instead of a single XP value. Useful regardless of which skill is being trained.

### 3. SWITCH_COMBAT_STYLE lunge DOES work

Previous session had issues where `stab` seemed to not work on superape. But this session confirmed:
- Sent `SWITCH_COMBAT_STYLE lunge` → command succeeded in logs
- Strength XP went from 1244 → 1352 (+108) while Attack stayed at 8408
- HP XP also went up (4276 → 4322) confirming kills happening

The earlier confusion was likely because the previous style switch happened mid-kill and the XP went to the old skill for kills already in progress.

### 4. GPT-5 Nano execution phase is unreliable

Two consecutive attempts with GPT-5 Nano resulted in 0 tool calls during execution. The model just says something without actually calling tools. Pattern from previous session: it works sometimes (1 tool call), fails sometimes (0 calls, or gives up after 6).

**Workaround:** Send critical setup commands (SWITCH_COMBAT_STYLE, KILL_LOOP) via MCP directly before starting the driver. Use the driver purely for monitoring mode.

**Caveat:** User prefers driving everything through the driver ("you are me normally"). Multi-phase goals (train Str to 25 → switch to Def → move to cows) require external orchestration since monitoring has no goal awareness.

### 5. Stale state files ≠ dead client

Monkey's state file was 5 hours stale (`/tmp/manny_monkey_state.json` last modified 20:05), but the command processor was still writing logs. This means:
- State writer component crashed while command processor still runs
- `send_and_await` fails (relies on state file) but `send_command` + log checking still works
- `get_game_state` MCP tool also worked - may have a fallback or different read path

**Don't assume:** "stale state = client down". Check the actual process and logs.

### 6. Monkey wasn't even running

After investigating monkey's KILL_LOOP failures (100/100 failed cow searches), turns out the monkey RuneLite client wasn't running at all! The command file was being written but nobody was reading it. The logs being written were from the previous session's still-running command processor thread.

**Lesson:** Always verify the client is actually running before debugging command failures. Check `runelite_status(account_id="monkey")` or verify state file freshness.

## Key Insights

### Driver Architecture Gap: Multi-Phase Goals

Current architecture:
```
User → Claude Code → manny-driver(directive) → LLM → MCP tools → game
                                              ↓
                                     monitoring mode (no LLM)
                                     - polls state every 30s
                                     - deterministic fixes only
                                     - no goal awareness
```

The monitoring can't handle: "Train Str to 25, then switch to Def, then move to cows."

**Options (not yet implemented):**
1. Accept structured goals: `{"phases": [{"skill": "strength", "target": 25, "style": "lunge"}, ...]}`
2. Re-engage LLM at milestones instead of deterministic-only monitoring
3. External orchestrator polls XP and restarts driver with new directives

Option 3 is what we're doing now (Claude Code as orchestrator), but it requires an active conversation.

## Files Modified

| File | Change |
|------|--------|
| `manny_driver/agent.py:359-373` | Status line: `atk_xp=N` → `cmb=A/S/D` (levels) |

## Anti-Patterns

1. **Don't hardcode a single skill in monitoring display** - Show all relevant skills or total XP delta
2. **Don't assume stale state file means client is down** - Check logs and process separately
3. **Don't debug KILL_LOOP failures without first verifying the client is running**
4. **Don't bypass the driver with raw MCP commands** (unless necessary for setup) - breaks the autonomy model
