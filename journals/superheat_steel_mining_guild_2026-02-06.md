# Superheat Steel Bars - Mining Guild F2P Iron Rock Targeting Failure

**Date:** 2026-02-06
**Context:** Perfecting the superheat steel bars routine in Mining Guild F2P section

## Summary

MINE_ORE iron repeatedly failed at F2P Mining Guild iron rocks. Initial assumption was rock depletion from competition - this was wrong. The real cause was the object location cache targeting members-area iron rocks instead of nearby F2P ones.

## Root Cause

### The Bug: Object Cache + Mixed Object IDs

Iron ore is configured with 4 object IDs:
```java
// PlayerHelpers.java line 306
new OreData("Iron", 15, 35.0, 100,
    new int[]{11364, 11365, 2092, 2093})
//              ^^F2P rocks^^  ^^Members rocks^^
```

`findGameObjectByIdWithCache()` returns the **first cached hit**, not the closest. Members-area rocks at (3024, 9726) got cached from loaded chunks and were returned over F2P rocks at (3032, 9739) that were 2 tiles away.

On retry after failure, `findGameObjectById()` searched around the **cached location** (members area) instead of rescanning the scene. The character kept walking toward the members gate, failing, camera-scanning to find the right rock, but internally still using the stale cache hint.

### Proof the Rocks Were Minable

Menu log from an attempt showed both options available:
```
[12] 'Mine' | 'Rocks'        <- depleted rock (system picked this)
[13] 'Mine' | 'Iron rocks'   <- MINABLE rock (correct, but skipped)
```

The interaction system matched index 12 first (depleted "Rocks") because the menu matcher returns the first match for action "Mine".

### Existing Infrastructure That Could Have Prevented This

1. **F2PMask.java** - Already has Mining Guild P2P boundaries defined, but only used for pathfinding, NOT for object discovery
2. **NPCSearchOptions.withinArea()** - Already has `areaBounds` filtering for NPC search, proving the pattern works. Objects just don't have it.

## BAD vs GOOD Patterns

### BAD: Assume depletion without proof
```python
# Iron mining fails...
# "Must be depleted from competition" <- WRONG ASSUMPTION
# Try again, fail again, assume crowded world
```

### GOOD: Check logs immediately, scan rocks
```python
# Iron mining fails...
get_logs(grep="MINE_ORE")     # Shows: targeting (3024, 9726) - MEMBERS AREA!
scan_tile_objects("Iron rocks") # Shows: F2P rocks at (3032, 9739) with id=11365 - MINABLE
# Real cause: cache targeting wrong rocks, not depletion
```

### BAD: GOTO workaround for cache bug
```python
# Walk to iron rocks first so cache finds them
send_command("GOTO 3033 9738 0")  # Naive - works but fragile
send_command("MINE_ORE iron 1")
```

### GOOD: Fix at engine level with F2PMask filtering
```java
// In findGameObjectsById(), after distance check:
if (F2PMask.isEnabled() && F2PMask.isBlocked(worldX, worldY)) {
    continue; // Skip P2P objects when in F2P mode
}
```

## Key Debugging Technique

**MCP `get_logs()` returned empty** for account-specific instances. Raw log tailing was the reliable fallback:
```bash
tail -30 /tmp/runelite_main.log
grep -i "iron\|MINE_ORE\|cache\|members" /tmp/runelite_main.log | tail -20
```

The critical log line that revealed the bug:
```
[PREPARE-OBJECT] Finding 'Iron rocks' (ID: 11365) near (3024, 9726)
```
That `near (3024, 9726)` is the cached members-area location being used as a search hint.

## Successful Workaround (Temporary)

Walking to (3033, 9738) before MINE_ORE iron - center of the F2P iron rock cluster - ensures the cache finds F2P rocks first. Ran 6 consecutive successful loops with this pattern:

| Loop | Coal | Iron | Superheat | Position After |
|------|------|------|-----------|----------------|
| 1 | OK (19s) | OK (11s) | OK | (3034, 9739) F2P |
| 2 | OK (22s) | OK (11s) | OK | (3032, 9736) F2P |
| 3 | OK (12s+22s) | OK (11s) | OK | (3032, 9738) F2P |
| 4 | OK (15s+22s) | OK (10s) | OK | (3031, 9739) F2P |
| 5 | OK (14s+30s) | OK (12s) | OK | (3033, 9736) F2P |
| 6 | OK (12s+30s) | OK (in progress) | - | F2P |

## Planned Fixes

1. **F2PMask filtering in `findGameObjectsById()`** - ~3 lines in GameEngine.java. Filters out P2P objects when F2P mode is active. Fixes all object lookups system-wide.
2. **Optional `bounds` param for MINE_ORE** - Like NPCSearchOptions.withinArea(), allows explicit area restriction per command.
3. **Camera zoom presets** - MINE_ORE hardcodes zoom_in=15 (max zoom). Need named presets (MINING=12, DEFAULT=5, etc.) in CameraSystem.java.
4. **YAML routine handler inner/outer loops** - Python execute_routine() needs to support the loop.inner/loop.outer structure for MCP-monitored autonomous execution.

## Additional Issues Found

- **`send_and_await` timing**: Coal mining takes 8-22s. Await conditions frequently timeout even when mining succeeds, due to polling gap between command completion and state check.
- **GOTO "already at destination"**: GOTO considers 3 tiles as arrived, but `location:X,Y` condition also uses 3 tiles. At exactly ~3.16 tiles, GOTO succeeds but the condition fails.
- **`query_nearby` returns empty**: The MCP tool sends `SCAN_OBJECTS` without arguments to the plugin, which errors. Separate bug in the MCP tool.

## Files Referenced

- `manny_src/utility/GameEngine.java` - findGameObjectsById() (line 1736), NPCSearchOptions (line 130)
- `manny_src/utility/PlayerHelpers.java` - handleMineOre() (line 20589), MiningHelper.findAvailableRocks() (line 29569)
- `manny_src/utility/F2PMask.java` - isBlocked() (line 92), Mining Guild P2P regions
- `manny_src/utility/ObjectLocationCache.java` - Cache system causing stale location hints
- `manny_src/utility/InteractionSystem.java` - interactWithGameObject() (line 123)
- `manny_src/utility/CameraSystem.java` - stabilizeCamera(), zoom control
- `routines/skilling/superheat_steel_bars.yaml` - Step 11 GOTO updated to (3033, 9738)
