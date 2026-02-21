# Driver Combat Monitoring Gaps - Lessons Learned
**Date:** 2026-02-08

## The Problem

Autonomous combat training via manny-driver had multiple failures: KILL_LOOP kept dying silently, XP went to the wrong skill, and the monitoring system couldn't handle combat style transitions. The human operator had to intervene repeatedly to fix what should have been autonomous.

## Root Cause

Three separate bugs compounded:

1. **Hardcoded NPC in idle recovery** (`agent.py:420-427`): XP idle detection restarted `KILL_LOOP Chicken none` regardless of what the directive said. Code was fixed to extract target from directive via regex, but the running process had the OLD code in memory.

2. **Wrong combat style**: Bronze sword defaults to "block" (Defence training). The LLM driver was told "train Attack style" but Gemini Flash Lite didn't send `SWITCH_COMBAT_STYLE stab` - it just started KILL_LOOP and assumed Attack was default.

3. **No skill-level-aware monitoring**: When Attack hit 30, nothing in the driver knew to switch to Strength. Claude Code (the outer orchestrator) had to send `SWITCH_COMBAT_STYLE lunge` directly via MCP, completely bypassing the LLM driver. This breaks the autonomy model.

## Key Lessons

### 1. Code changes don't apply to running processes

**What happened:** Fixed the hardcoded Chicken in `agent.py`, but the driver was already running with the old code in memory. It kept sending `KILL_LOOP Chicken none` at the cow field - finding zero chickens and looping on "No NPCs named 'Chicken' found" for 30+ attempts.

**Why:** Python loads modules at startup. Editing files on disk doesn't affect running processes.

**Solution:** Must restart the driver after code changes. There's no hot-reload.

```python
# The fix (agent.py _check_monitoring_triggers):
# BAD - hardcoded target
return ("xp_idle", ["KILL_LOOP Chicken none"])

# GOOD - extract from directive
import re
directive = self._current_directive or self._original_goal or ""
m = re.search(r'KILL_LOOP\s+(\S+)', directive)
if not m:
    m = re.search(r'kill(?:ing)?\s+(\w+)', directive, re.IGNORECASE)
target = m.group(1).rstrip('s') if m else "Cow"
return ("xp_idle", [f"KILL_LOOP {target} none"])
```

### 2. Combat style names are weapon-specific

**What happened:** `SWITCH_COMBAT_STYLE accurate` failed with "not found in group 593". Bronze sword uses weapon-specific style names, not generic ones.

**Why:** OSRS combat styles vary by weapon type. The widget text matches the style name exactly.

**Solution:**
```
# BAD - generic names don't exist on all weapons
SWITCH_COMBAT_STYLE accurate    # fails on swords
SWITCH_COMBAT_STYLE aggressive  # fails on swords

# GOOD - use the actual widget text for the weapon
# Bronze sword styles:
SWITCH_COMBAT_STYLE stab   # Attack XP
SWITCH_COMBAT_STYLE lunge  # Strength XP
SWITCH_COMBAT_STYLE slash  # Strength XP
SWITCH_COMBAT_STYLE block  # Defence XP
```

### 3. Monitoring has no goal awareness

**What happened:** Attack hit 30 (the target), but monitoring kept going. The outer orchestrator (Claude Code) had to manually send `SWITCH_COMBAT_STYLE lunge` via MCP, bypassing the LLM driver entirely.

**Why:** `_check_monitoring_triggers` only checks:
- Inventory full (deterministic: bury bones, drop junk)
- Health critical (LLM intervention)
- XP idle (deterministic: restart KILL_LOOP)

It has NO concept of "target level reached, switch to next skill."

**Gap:** The monitoring system needs goal-aware triggers. Options:
1. Accept a structured goal (e.g., `{"attack": 30, "strength": 30, "defence": 30}`) and monitor skill levels
2. Re-engage LLM when a skill milestone is reached
3. Add deterministic combat-style rotation in `_check_monitoring_triggers`

### 4. Monitoring status line only shows atk_xp

**What happened:** After switching to Strength training, the status line still shows `atk_xp=13584` (unchanged). Misleading - looks like the bot is idle when it's actually gaining Strength XP.

**Why:** Hardcoded in `agent.py` run_monitoring:
```python
atk = skills.get("attack", {})
# ...
f"atk_xp={atk.get('xp','?')}"
```

**Fix needed:** Show XP for the actively-trained skill, or show total XP delta.

### 5. GPT-5 Nano works great for this use case

**What happened:** Switched from Gemini Flash Lite ($0.10/$0.40 per M) to GPT-5 Nano ($0.05/$0.40 per M). First request used only 1 tool call (vs 23 with Gemini). Total cost for 2.5 hours of training: $0.0018.

**Why:** Monitoring mode doesn't call the LLM at all - it polls `get_game_state` directly via MCP. The LLM is only used for initial setup and interventions. At ~1 intervention per hour, the model choice barely matters for ongoing cost.

**Key insight:** The monitoring architecture makes model cost nearly irrelevant. The real cost driver is execution phase tool calls, and GPT-5 Nano was more efficient (1 call vs 23) at understanding "just start monitoring."

### 6. MCP get_logs returns empty for account-specific instances

**What happened:** `get_logs(account_id="monkey")` returned empty arrays, even when the plugin was actively logging KILL_LOOP attempts.

**Why:** Known MCP server bug with account-specific log file paths.

**Workaround:**
```bash
# Use tail directly on the account-specific log
tail -50 /tmp/runelite_monkey.log
```

This is how we discovered the "KILL_LOOP Chicken" bug - the MCP tool showed nothing, but the raw log file showed 30+ failed Chicken search attempts.

## Anti-Patterns

1. **Don't assume combat style defaults** - Always explicitly set the combat style before starting KILL_LOOP. Different weapons have different default styles.
2. **Don't edit agent.py and expect running drivers to change** - Must restart the process.
3. **Don't rely on get_logs for account instances** - Use `tail /tmp/runelite_<account>.log` as fallback.
4. **Don't bypass the LLM driver with direct MCP commands** - This breaks the autonomy model. If the monitoring can't handle something, add it to monitoring, don't work around it.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail -50 /tmp/runelite_monkey.log` | Raw plugin logs (bypasses MCP bug) |
| `get_game_state(fields=["skills"])` | Check actual skill levels/XP |
| `tail -5 /tmp/manny_driver_requests.jsonl` | Check LLM costs per request |
| `SWITCH_COMBAT_STYLE <style>` | Style names: check combat tab widget text |

## Interface Gaps Identified

- [ ] **Monitoring needs goal-aware triggers**: Accept target levels, auto-switch combat style when milestones reached
- [ ] **Monitoring status line should show active skill XP**, not hardcoded `atk_xp`
- [ ] **get_logs MCP bug**: Returns empty for account-specific instances
- [ ] **No hot-reload for agent code**: Must restart entire driver process for code changes
- [ ] **Combat fragment says "default style trains ATTACK"** - This is wrong; it depends on the weapon. Fragment needs updating.

## Files Modified

| File | Change |
|------|--------|
| `manny_driver/agent.py:420-427` | Fixed hardcoded Chicken → extract target from directive via regex |
| `manny_driver/config.py` | Added `gpt-5-nano` pricing ($0.05/$0.40), updated OpenAI default |
| `manny_driver/llm_client.py:326` | Changed `max_tokens` → `max_completion_tokens` for GPT-5 Nano |
| `manny_driver/context_fragments/combat.md` | Needs update: wrong info about default combat style |

## Cost Data

| Provider | Model | Execution Cost | Monitoring Cost | Total (2.5hr) |
|----------|-------|---------------|-----------------|---------------|
| Gemini | flash-lite | $0.0298 (23 calls) | $0/hr | $0.0298 |
| OpenAI | gpt-5-nano | $0.0018 (1 call) | $0/hr | $0.0018 |

Monitoring mode is free because it polls game state directly via MCP without LLM calls. The LLM only fires during execution phase and interventions.
