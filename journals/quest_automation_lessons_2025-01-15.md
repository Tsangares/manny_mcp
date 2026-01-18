# Quest Automation Lessons - Sheep Shearer

**Date:** 2025-01-15
**Quest:** Sheep Shearer (1 QP)
**Status:** Completed successfully

## Critical Discovery: Object Naming Convention

### The Problem
`INTERACT_OBJECT Spinning wheel Spin` failed silently. Logs showed:
```
[INTERACT_OBJECT] wheel Spin on Spinning
```

The command parser split on spaces, treating "Spinning" as the object and "wheel Spin" as the action.

### The Fix
**Multi-word object names MUST use underscores in INTERACT_OBJECT:**

```python
# BAD - spaces cause parsing errors
send_command("INTERACT_OBJECT Spinning wheel Spin")

# GOOD - underscores work correctly
send_command("INTERACT_OBJECT Spinning_wheel Spin")
```

### Convention Table
| Command | Name Format | Example |
|---------|-------------|---------|
| INTERACT_OBJECT | Underscores | `Large_door`, `Spinning_wheel`, `Cooking_range` |
| INTERACT_NPC | Underscores | `Fred_the_Farmer`, `Captain_Tobias` |
| Item names (inventory) | Spaces | `Ball of wool`, `Raw shrimps` |

**Always scan first** to get exact names:
```python
scan_tile_objects("wheel")  # Returns: "Spinning_wheel"
query_nearby(name_filter="Fred")  # Returns: "Fred the Farmer"
```

## New Feature: Dialogue State in Game State

The manny state file now includes dialogue information:

```json
"dialogue": {
  "open": true,
  "type": "npc_chat",
  "speaker": "ArmAndALegs",
  "text": "Click here to continue",
  "options": [],
  "hint": "CLICK_CONTINUE"
}
```

**Benefits:**
- No need for screenshots to check dialogue state
- `hint` field suggests action: `CLICK_CONTINUE`, `SELECT_OPTION`
- More efficient than separate `get_dialogue()` calls

**Usage:**
```python
state = get_game_state()
if state["dialogue"]["hint"] == "CLICK_CONTINUE":
    click_continue()
```

## Sheep Shearing: Retry Logic Needed

### The Problem
Not all sheep have wool. Sheared sheep have no "Shear" action available.

### Symptoms
- `INTERACT_NPC Sheep Shear` fails with "action not found"
- Different sheep IDs (1308, 2787, 1299, etc.) - some woolly, some sheared

### Solution
For YAML routines, need retry logic:
1. Attempt shear
2. If fails, move to different part of pen
3. Retry with different sheep
4. Sheep respawn with wool after ~2 minutes

## Camera Zoom Issues

### The Problem
NPC interactions zoom in automatically for targeting. After multiple interactions, camera becomes too close.

### Solution
Use `stabilize_camera()` after NPC-heavy sequences:
```python
# After shearing 20 sheep
stabilize_camera()  # Resets to comfortable medium zoom
```

## Navigation: Waypoints for Long Distances

### The Problem
`GOTO` can timeout on paths >20 tiles, especially with obstacles.

### Solution
Break long paths into segments:
```python
# BAD - may timeout
send_command("GOTO 3189 3276 0")  # 30+ tiles

# GOOD - intermediate waypoints
send_command("GOTO 3200 3250 0")  # First segment
send_command("GOTO 3189 3276 0")  # Second segment
```

## Quest Dialogue Patterns

Sheep Shearer dialogue flow:
1. Talk to Fred -> Continue
2. Select "I need to talk to you about shearing these sheep!"
3. Multiple continues through explanation
4. Turn in wool -> Continue x5
5. Quest complete screen

**For YAML routines:**
- Use `DIALOGUE_SELECT` for option selection
- Use `DIALOGUE_CONTINUE` with repeat count for multiple continues

## Files Modified

- `CLAUDE.md`: Added Object Naming Rules section
- `routines/quests/sheep_shearer.yaml`: Full validated routine

## Summary

| Issue | Root Cause | Fix |
|-------|------------|-----|
| Object interaction fails | Space in name | Use underscores |
| Sheep shearing fails | Already sheared | Move + retry |
| Camera too close | Auto-zoom | `stabilize_camera()` |
| Pathing timeout | Long distance | Use waypoints |
