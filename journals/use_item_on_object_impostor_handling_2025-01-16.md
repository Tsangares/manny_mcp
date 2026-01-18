# USE_ITEM_ON_OBJECT Impostor Objects - Lessons Learned
**Date:** 2025-01-16

## The Problem

`USE_ITEM_ON_OBJECT Ghost's skull coffin` failed with "Object not found or not clickable" even though `scan_tile_objects("coffin")` found the coffin 2 tiles away. The command `INTERACT_OBJECT Coffin Open` worked fine on the same object.

## Root Cause

OSRS objects with multiple states (open/closed doors, chests, coffins) use **impostor IDs**. The base `ObjectComposition` from `client.getObjectDefinition(id)` may return null or a different name, but calling `comp.getImpostor()` returns the actual transformed state with the correct name.

**Working code** (`ScanTileObjectsCommand.java:226-228`):
```java
ObjectComposition comp = client.getObjectDefinition(id);
if (comp != null && comp.getImpostorIds() != null)
{
    comp = comp.getImpostor();  // Gets actual name for transformed objects
}
```

**Broken code** (`PlayerHelpers.java:14453-14455`):
```java
ObjectComposition comp = client.getObjectDefinition(gameObj.getId());
if (comp != null && comp.getName() != null &&
    comp.getName().equalsIgnoreCase(objectName))  // Name is null/wrong for impostors!
```

The coffin, when opened, has an impostor ID. Without calling `getImpostor()`, `comp.getName()` returned something other than "coffin".

## Key Lessons

### 1. Always Handle Impostors When Looking Up Object Names

**What happened:** Object name lookup failed for transformed objects (doors, chests, coffins).
**Why:** Base ObjectComposition doesn't have the current state's name - the impostor does.
**Solution:**
```java
// BAD - fails for transformed objects
ObjectComposition comp = client.getObjectDefinition(obj.getId());
if (comp.getName().equalsIgnoreCase(targetName)) { ... }

// GOOD - handles all object states
ObjectComposition comp = client.getObjectDefinition(obj.getId());
if (comp != null && comp.getImpostorIds() != null)
{
    comp = comp.getImpostor();
}
if (comp != null && comp.getName() != null &&
    comp.getName().equalsIgnoreCase(targetName)) { ... }
```

### 2. Inconsistent Patterns Across Commands Cause Bugs

**What happened:** `INTERACT_OBJECT` used `interactionSystem.interactWithGameObject()` (which handles impostors), but `USE_ITEM_ON_OBJECT` had inline scene iteration that didn't.
**Why:** Copy-paste of scene iteration code without copying the impostor handling.
**Solution:** Either use the established wrappers (`interactionSystem`, `gameHelpers`) or ensure inline code matches their patterns.

### 3. "Command Executed Successfully" Can Be Misleading

**What happened:** Logs showed success before the actual execution failed:
```
[background-2] INFO  - Command executed successfully: USE_ITEM_ON_OBJECT
[background-1] ERROR - Object not found or not clickable: coffin
```
**Why:** `handleUseItemOnObject` returns `true` immediately after submitting to background executor, not after execution completes.
**Implication:** Always check for the actual success log (`Successfully used X on Y`) or use `get_command_response()`.

## Anti-Patterns

1. **Don't inline scene iteration without impostor handling** - Transformed objects (doors, chests, coffins) won't be found
2. **Don't trust "Command executed successfully" alone** - Check for the actual action completion log
3. **Don't assume object name matching is simple** - OSRS objects have complex state systems

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `scan_tile_objects("coffin")` | Verify object exists and get exact name (handles impostors) |
| `get_logs(level="ALL", grep="USE_ITEM")` | See full execution chain including errors |
| `get_command_response()` | Check actual success/failure response |

## Interface Gaps Identified

- [x] Plugin fix: Added impostor handling to all 4 object type checks in `handleUseItemOnObject`

## Pattern Reference

Commands/methods that properly handle impostors:
- `ScanTileObjectsCommand.getObjectComposition()`
- `GameEngine.findTileObjectsByName()`
- `InteractionSystem.interactWithGameObject()` (via GameEngine)

Commands that needed fixing:
- `handleUseItemOnObject()` - now fixed

**When adding new object lookup code**, always include:
```java
if (comp != null && comp.getImpostorIds() != null)
{
    comp = comp.getImpostor();
}
```

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/PlayerHelpers.java:14454-14458` | Added impostor handling for GameObject |
| `manny_src/utility/PlayerHelpers.java:14477-14481` | Added impostor handling for GroundObject |
| `manny_src/utility/PlayerHelpers.java:14500-14504` | Added impostor handling for WallObject |
| `manny_src/utility/PlayerHelpers.java:14523-14527` | Added impostor handling for DecorativeObject |
