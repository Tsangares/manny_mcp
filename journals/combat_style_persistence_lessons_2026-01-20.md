# Combat Style Persistence - Lessons Learned
**Date:** 2026-01-20

## The Problem

After switching from Attack to Strength training and restarting the combat routine, XP was still going to Attack instead of Strength. 15 minutes of training were wasted before noticing.

## Root Cause

Combat style selection is **client-side state**, not routine state. When:
1. We clicked "Slash" for Strength training
2. Then started `execute_combat_routine()`
3. The routine dispatched but didn't preserve/verify combat style

The combat style widget click happened, but either:
- The click didn't register before routine started
- A routine restart/player death reset the style
- The style reverted when the Combat Options tab closed

## Key Lessons

### 1. Verify Combat Style After Routine Start

**What happened:** Assumed clicking "Slash" widget was sufficient
**Why:** Combat style is independent of the combat routine - routine just handles targeting and looting
**Solution:**
```python
# BAD - assume style persists
click_widget(38862858)  # Slash
execute_combat_routine(...)
sleep(900)  # 15 min of wrong training!

# GOOD - verify style is actually active
click_widget(38862858)  # Slash
execute_combat_routine(...)
sleep(60)  # Short wait
state = get_game_state(fields=["skills"])
# Check that target skill XP increased, not wrong skill
```

### 2. Use XP Delta to Verify Training Mode

**What happened:** Didn't check which skill was gaining XP until 15 min in
**Why:** Combat state shows "IDLE" between kills - not useful for verifying training mode
**Solution:**
```python
# Capture baseline
baseline_str = state["skills"]["strength"]["xp"]
baseline_atk = state["skills"]["attack"]["xp"]

# After 1-2 kills (~60 sec)
new_state = get_game_state(fields=["skills"])

# Verify correct skill is training
str_delta = new_state["skills"]["strength"]["xp"] - baseline_str
atk_delta = new_state["skills"]["attack"]["xp"] - baseline_atk

if atk_delta > str_delta and intended_style == "Strength":
    # WRONG STYLE - fix it
    set_combat_style("Slash")
```

### 3. Combat Styles Map to Skills

| Style | Trains | Widget Action |
|-------|--------|---------------|
| Chop (Accurate) | Attack | widget 38862850 |
| Slash (Aggressive) | Strength | widget 38862858 |
| Lunge (Controlled) | Shared | widget 38862854 |
| Block (Defensive) | Defence | widget 38862862 |

Note: Widget IDs are for Rune scimitar. Different weapons have different combat interfaces.

## Anti-Patterns

1. **Don't** assume combat style persists across routine restarts - always verify
2. **Don't** wait 15+ minutes before checking XP deltas - verify within first 1-2 minutes
3. **Don't** trust "combat state: IDLE" as an indicator of anything - it's just between kills

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_game_state(fields=["skills"])` | Check XP to verify which skill is training |
| `find_widget(text="Slash")` | Find combat style button |
| `scan_widgets(group=593)` | Scan entire Combat Options interface |

## Interface Gaps Identified

- [ ] Plugin needs: `GET_COMBAT_STYLE` command to query current style
- [ ] Plugin needs: `SET_COMBAT_STYLE <style>` command that verifies the change
- [ ] MCP needs: Combat routine should optionally accept and enforce a combat style
- [ ] CLAUDE.md needs: Document combat style verification pattern

## Potential Enhancement

The combat routine YAML could include a `combat_style` field:
```yaml
name: "Hill Giants - Strength Training"
npc: "Hill Giant"
combat_style: "Slash"  # Routine would verify/set this
kills: 500
```

This would eliminate the manual style management and potential for training wrong skill.
