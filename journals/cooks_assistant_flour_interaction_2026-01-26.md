# Cook's Assistant Flour Mill - Lessons Learned
**Date:** 2026-01-26

## The Problem

Multiple commands failed during flour-making at the windmill: `USE_ITEM_ON_OBJECT Pot Flour_bin` didn't work, `INTERACT_OBJECT Hopper controls Operate` failed, and game chat messages ("The grain slides down the chute") couldn't be read programmatically.

## Root Cause

1. **Flour bin interaction**: The flour bin has an "Empty" action, not "Use" - you interact with it directly while holding a pot, rather than using the pot ON it.
2. **Object naming**: "Hopper controls" has a space in the YAML routine but needs underscore for `INTERACT_OBJECT`.
3. **Chat messages**: No MCP tool exists to read game chat widget messages.

## Key Lessons

### 1. Flour Bin Uses "Empty" Action, Not USE_ITEM_ON_OBJECT

**What happened:** `USE_ITEM_ON_OBJECT Pot Flour_bin` timed out with no visible effect.
**Why:** The flour bin is interacted with directly via right-click "Empty" while pot is in inventory.
**Solution:**
```python
# BAD - Pot isn't "used on" flour bin
send_command("USE_ITEM_ON_OBJECT Pot Flour_bin")  # Times out

# GOOD - Interact directly, game auto-uses pot from inventory
send_command("INTERACT_OBJECT Flour_bin Empty")  # Works
```

### 2. Scan Objects to Find Exact Names

**What happened:** `query_nearby(name_filter="flour")` returned empty, but `scan_tile_objects("flour")` found the bin.
**Why:** Different tools search different object types. `scan_tile_objects` is more thorough.
**Solution:**
```python
# When query_nearby fails, use scan_tile_objects
scan_tile_objects(object_name="flour", max_distance=10)
# Returns: [{"name": "flour", "id": 1781, "type": "GameObject", ...}]
```

### 3. Hopper Controls Need Underscore in Command

**What happened:** `INTERACT_OBJECT Hopper controls Operate` failed to find object.
**Why:** Parser splits on spaces. "Hopper controls" becomes object="Hopper", action="controls Operate".
**Solution:**
```python
# BAD - Space causes parsing error
send_command("INTERACT_OBJECT Hopper controls Operate")

# GOOD - Underscore for multi-word object names
send_command("INTERACT_OBJECT Hopper_controls Operate")
```

## Anti-Patterns

1. **Don't assume USE_ITEM_ON_OBJECT** for all containers - some use direct interaction (Empty, Fill, etc.)
2. **Don't use spaces in multi-word object names** - Always use underscores for INTERACT_OBJECT

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `scan_tile_objects("name")` | Find exact object names when query_nearby fails |
| `get_screenshot()` | Read chat messages visually (only current option) |
| `get_logs(grep="INTERACT")` | Check if command was received and parsed |

## Interface Gaps Identified

- [ ] **MCP needs: `get_chat_messages()`** - Read game chat widget programmatically. Would help detect:
  - "The grain slides down the chute" (hopper success)
  - "You need a pot to collect flour" (missing item)
  - Quest dialogue hints
- [ ] **CLAUDE.md needs:** Document that flour bin uses "Empty" action, not USE_ITEM_ON_OBJECT

## Files Modified

| File | Change |
|------|--------|
| `routines/quests/cooks_assistant.yaml` | Needs fix: step 21 should be `INTERACT_OBJECT Flour_bin Empty` |
