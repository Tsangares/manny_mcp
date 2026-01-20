# Al Kharid Warrior Training - Session Summary
**Date:** 2025-01-13

## Overview

Trained Attack from 43 to 45 and Defence from 37 to 40 at Al Kharid Warriors. The session was highly efficient - **zero food consumed** despite carrying 22 lobsters as backup.

## Goals Achieved

| Skill | Start | End | XP Gained |
|-------|-------|-----|-----------|
| Attack | 43 (51,000~) | 45 (61,674) | ~10,600 |
| Defence | 37 (35,000~) | 40 (37,422) | ~2,400 |
| Hitpoints | 42 | 43 (54,569) | ~1,400 |

## Why Al Kharid Warriors Work

**Location:** (3285-3301, 3168-3176, 0) - courtyard near Al Kharid palace

**Target:** Al Kharid warrior (Level 9, NPC ID 3292)

**Advantages:**
- Low level (9) = high hit rate, fast kills
- Multiple spawn points = minimal downtime
- Open area = good pathing, few LOS issues
- Near bank if resupply needed

## Key Lesson: Adamant Armor Trivializes Level 9 Warriors

**Equipment used:**
- Adamant full helm, platebody, platelegs, kiteshield
- Adamant mace (crush, with prayer bonus)
- Amulet of strength

**Result:** Warriors hit so rarely and for so little damage that natural HP regeneration outpaced incoming damage. HP fluctuated between 28-43 throughout the session without ever needing to eat.

**Implication:** For gear-appropriate training spots, food is insurance rather than necessity. Don't over-prepare with expensive food for trivial content.

## KILL_LOOP Behavior Pattern

**Observation:** The `KILL_LOOP Al_Kharid_warrior 40` command consistently stops after 1-3 minutes despite warriors being available.

**Workaround:** Restart the loop every 3 minutes during monitoring cycles.

**Monitoring pattern used:**
```python
# Every 3 minutes:
get_game_state()  # Check XP progress
send_command("KILL_LOOP Al_Kharid_warrior 40")  # Restart loop
# Wait 3 minutes, repeat
```

**XP rates observed:** 150-250 XP per 3-minute cycle when loop was active.

**Root cause:** Unknown. The scenario shows "Idle" but combat state sometimes shows "FIGHTING" or "EVALUATING". May be related to:
- Target selection timeout after killing current target
- Scenario state management issues
- Combat state machine edge cases

**Not investigated further** - the restart workaround is simple and effective.

## Combat Style Switching

Switched between Attack and Defence XP by clicking combat style widgets:

| Style | Widget ID | XP Type |
|-------|-----------|---------|
| Pound (Accurate) | 38862854 | Attack |
| Block (Defensive) | 38862866 | Defence |

**Method:** `send_command("CLICK_WIDGET 38862854")` to switch styles.

## Position Management

**Issue:** Player occasionally wandered near palace walls, causing LOS errors ("blocked by WALL").

**Solution:** Periodically reposition to center of warrior spawn area:
```python
send_command("GOTO 3285 3171 0")
```

This keeps the player in the open courtyard with good access to all warrior spawns.

## Random Events

**Mysterious Old Man** appeared once during the session. Attempted dismiss with:
```python
send_command("INTERACT_NPC Mysterious_Old_Man Dismiss")
```

Event eventually disappeared on its own. No significant disruption.

## Session Statistics

- **Total training time:** ~2 hours (across multiple context windows)
- **Food consumed:** 0 of 22 lobsters
- **Deaths:** 0
- **Manual interventions:** Periodic loop restarts only
- **XP efficiency:** Very high for the combat level

## Recommendations for Future Sessions

1. **Gear matters more than food** - With appropriate armor, low-level content becomes trivial
2. **Monitor in 3-minute cycles** - Check state, restart loop, repeat
3. **Stay centered** - Avoid walls and corners to prevent LOS issues
4. **Track XP per cycle** - If gaining <100 XP per cycle, loop is stuck
5. **HP threshold 40** - Good balance for level 9 warriors; allows natural regen

## Files Referenced

- Combat loop: `PlayerHelpers.java` - `handleKillLoop()` method
- Combat system: `CombatSystem.java` - NPC targeting and attack logic

## Next Steps

With Attack 45, Defence 40, Strength 40:
- Could continue to Strength 45 or Defence 45
- Consider upgrading to rune equipment at Attack 40+
- Could move to slightly higher level targets for better XP rates
