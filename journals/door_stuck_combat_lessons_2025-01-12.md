# Door-Stuck Combat Detection - Lessons Learned
**Date:** 2025-01-12

## The Problem

Combat system targets NPCs behind closed doors. Player walks to the door, gets stuck with "I can't reach that!" spam in chat, and combat loop fails repeatedly without recovery. This causes the KILL_LOOP to waste iterations and eventually trigger roaming behavior that moves the player away from valid targets.

## Root Cause

The LOS (line-of-sight) check in `handleKillLoop` uses `worldMapData` to detect walls and gates, but this is **static map data**. Closed doors are **dynamic obstacles** - they exist as TileObjects with an "Open" action that can be interacted with. The LOS check sees through doors because the underlying tile is walkable when the door is open.

**Code location:** `PlayerHelpers.java:16724-16762` (LOS checking loop)

The LOS check correctly identifies walls (`isWalkableGlobal`) and gates (`isGate`), but a closed door at a tile doesn't make that tile unwalkable in the static map data - it's a TileObject sitting on top of a walkable tile.

## Key Lessons

### 1. Stuck Detection Pattern: Position + Combat State

**What happened:** Combat command sent, but player didn't move and combat didn't start.

**Why:** When stuck at a door, the player walks to the door tile but can't path through to reach the NPC. They stop moving without entering combat.

**Solution:**
```java
// Track position BEFORE attack
WorldPoint preAttackPos = helper.readFromClient(() -> {
    Player player = client.getLocalPlayer();
    return player != null ? player.getWorldLocation() : null;
});

// After attack fails, check if stuck
WorldPoint postAttackPos = helper.readFromClient(...);
int distMoved = preAttackPos.distanceTo(postAttackPos);

// BAD - just increment failedKills and continue
failedKills++;
continue;

// GOOD - detect stuck state and try door opening
if (distMoved < 3) {  // Player barely moved
    log.info("[DOOR-STUCK] Player barely moved - checking for doors");
    if (findAndOpenNearbyDoor(5)) {
        // Retry attack after door opens
        result = combatSystem.attackNPC(target, npcName, 3, 60000);
    }
}
```

### 2. Door Detection: Actions Reveal State

**What happened:** Need to find closed doors vs already-open doors.

**Why:** Doors with "Open" action are closed. Doors with "Close" action are already open.

**Solution:**
```java
// Get actions from ObjectComposition
String[] actions = helper.readFromClient(() -> {
    ObjectComposition comp = client.getObjectDefinition(obj.getId());
    if (comp != null) {
        // Handle morphing objects (varbit state changes)
        ObjectComposition realComp = comp.getImpostorIds() != null
            ? comp.getImpostor() : comp;
        return realComp != null ? realComp.getActions() : null;
    }
    return null;
});

// Check for "Open" action = door is closed
boolean hasOpenAction = false;
for (String action : actions) {
    if (action != null && action.equalsIgnoreCase("Open")) {
        hasOpenAction = true;
        break;
    }
}
```

### 3. Door Types: Search Multiple Patterns

**What happened:** Searching just "door" misses "gate" and "fence" obstacles.

**Why:** Different obstacle types have different names but same blocking behavior.

**Solution:**
```java
// Search multiple patterns
String[] doorPatterns = {"door", "gate", "fence"};

for (String pattern : doorPatterns) {
    List<TileObject> candidates = gameHelpers.findTileObjectsByName(pattern, maxDistance);
    // ... check each for "Open" action
}
```

### 4. Doors are WallObjects, Not GameObjects

**What happened:** Initial attempt to find doors using GameObject search failed.

**Why:** Doors, gates, and fences are typically `WallObject` type, not `GameObject`.

**Solution:** Use `gameHelpers.findTileObjectsByName()` which searches ALL TileObject types:
- GameObject (normal scenery)
- WallObject (doors, gates, fences)
- DecorativeObject
- GroundObject

## Anti-Patterns

1. **Don't** use `interactionSystem.interactWithTileObject(obj, action)` - method doesn't exist. Use `interactWithGameObject(objectName, action, radius)` instead.

2. **Don't** assume doors are in the outer PlayerHelpers class - `handleKillLoop` is in the static inner `CommandProcessor` class. Methods accessing `interactionSystem` must be in CommandProcessor.

3. **Don't** rely only on LOS checking to filter unreachable NPCs - closed doors aren't detected by static map data.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="DOOR-STUCK")` | See door detection and opening attempts |
| `get_logs(grep="blocked by WALL")` | See LOS failures (but won't show door issues) |
| `scan_tile_objects(object_name="door")` | Find nearby doors and their actions |

## Interface Gaps Identified

- [x] Plugin needs: Door-stuck detection in combat loop (IMPLEMENTED)
- [x] Plugin needs: `findAndOpenNearbyDoor()` helper method (IMPLEMENTED)
- [ ] Plugin could use: Static LOS check that also queries nearby closed doors
- [ ] MCP could use: `is_stuck_at_door()` diagnostic tool

## Files Modified

| File | Change |
|------|--------|
| `PlayerHelpers.java:16489-16586` | Added `findAndOpenNearbyDoor(int maxDistance)` method in CommandProcessor |
| `PlayerHelpers.java:16920-16987` | Added stuck detection and door opening to `handleKillLoop` attack failure handling |

## Combat Flow After Fix

```
1. Attack NPC
2. If attack fails:
   a. Check if player barely moved (distMoved < 3)
   b. If stuck, call findAndOpenNearbyDoor(5)
   c. If door opened, retry attack on same target
   d. If no door found or retry fails, increment failedKills
3. Continue loop
```

## Testing Notes

- First test showed door opening working: `[DOOR-STUCK] ✓ Successfully opened door/gate at (3287, 3171)`
- Subsequent attack retry succeeded after door opened
- Menu clicking issue (clicking "Pickpocket" instead of "Attack") is a separate pre-existing bug, not related to door fix
