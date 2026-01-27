# Location History Enhancements - Lessons Learned
**Date:** 2026-01-26

## The Problem

Enhanced the location history system to support better YAML routine generation. The ticket requested: CLICK_CONTINUE recording, plane change detection, location labels, and waypoint consolidation.

## Root Cause

No single root cause - this was feature implementation. However, one compilation error taught a lesson about nested class references.

## Key Lessons

### 1. Nested Class `this` References

**What happened:** Added `playerHelpers` parameter to `ClickContinueCommand` constructor, but passed `this` from inside `CommandProcessor` (a nested static class in `PlayerHelpers.java`).

**Why:** Inside a static nested class, `this` refers to the nested class instance, not the outer class. The error message was:
```
incompatible types: PlayerHelpers.CommandProcessor cannot be converted to PlayerHelpers
```

**Solution:**
```java
// BAD - `this` refers to CommandProcessor, not PlayerHelpers
this.clickContinueCommand = new ClickContinueCommand(..., this);

// GOOD - Use the field that holds the outer class reference
this.clickContinueCommand = new ClickContinueCommand(..., playerHelpers);
```

**Pattern to remember:** In nested classes inside `PlayerHelpers`, use the `playerHelpers` field (line 9515) to pass the outer class reference.

### 2. Plane Change Detection via GameTick Polling

**What happened:** Needed to detect when player moves between planes (e.g., climbing stairs).

**Why:** Plane changes happen as a result of interactions, but the actual transition isn't immediate - it happens on subsequent game ticks.

**Solution:**
```java
// In LocationHistory class
private int lastPlane = -1;
private String lastInteractionTarget = null;

public void onGameTick() {
    int currentPlane = loc.getPlane();

    // Detect plane change
    if (lastPlane >= 0 && currentPlane != lastPlane) {
        recordPlaneChange(lastPlane, currentPlane, lastInteractionTarget);
    }
    lastPlane = currentPlane;
}

// In recordInteraction() - track the trigger
lastInteractionTarget = target + " " + action;  // e.g., "Ladder Climb-up"
```

**Key insight:** Store the last interaction as a potential trigger BEFORE the plane change happens. The change is detected on the next tick after the interaction completes.

### 3. Location Labels Using Bounds Checking

**What happened:** Added location labels by loading YAML files and checking if coordinates fall within defined room bounds.

**Why:** Location knowledge is stored as bounding boxes in `data/locations/*.yaml`.

**Solution:**
```python
# Bounds format: [min_x, min_y, max_x, max_y]
if min_x <= x <= max_x and min_y <= y <= max_y:
    return {"area": area_name, "room": room_name}
```

**Limitation:** Only works for defined areas. Most of the game world is unlabeled.

## Anti-Patterns

1. **Don't** use `this` in nested static classes when you need the outer class - use the field reference instead
2. **Don't** try to detect plane changes synchronously in interactions - use the next GameTick to observe the change
3. **Don't** modify position dicts in-place before calculating stats - keep original data for accurate statistics

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="EVENT")` | Verify Java is recording events |
| `get_event_history()` | Check Python reads events correctly |
| `generate_routine(routine_name="test")` | Verify YAML generation works |

## Interface Gaps Identified

Events now recorded:
- [x] INTERACT_NPC, INTERACT_OBJECT
- [x] CLICK_DIALOGUE (all paths)
- [x] CLICK_CONTINUE (added this session)
- [x] USE_ITEM_ON_OBJECT, PICK_UP_ITEM
- [x] BANK operations
- [x] Plane changes (added this session)

Still not recorded:
- [ ] Combat style changes (widget clicks)
- [ ] Inventory drop/equip via right-click menu

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/ClickContinueCommand.java` | Added PlayerHelpers param, record dialogue events |
| `manny_src/utility/PlayerHelpers.java:9766` | Wire playerHelpers to ClickContinueCommand |
| `manny_src/utility/GameEngine.java:9917-10230` | Added plane change tracking fields, `recordPlaneChange()` method, LocationEntry fields |
| `mcptools/tools/location_history.py` | Added `_load_location_data()`, `_add_location_labels()`, `_consolidate_movements()`, new tool params |
| `mcptools/tools/routine_generator.py` | Handle `plane_change` events, extract new event fields |

## Summary

The location history system now tracks more events for routine generation:
- **CLICK_CONTINUE** events with "continue" dialogue option
- **Plane changes** with from/to planes and trigger (e.g., "Ladder Climb-up")
- **Location labels** can be added to positions using `add_location_labels=True`
- **Waypoint consolidation** available via `consolidate_movements=True`
