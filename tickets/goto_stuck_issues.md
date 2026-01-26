# GOTO Navigation Stuck Issues

## Status: FIXED (2026-01-24)

## Summary
The GOTO command sometimes gets stuck when navigating in the Dwarven Mine, showing "Player stuck - no movement" errors even when a path appears to be computed.

## Root Cause Analysis

The pathfinder was using a 3-tier collision data system:
1. **Live Cache** - Only tiles player has visited
2. **Extracted Cache** - Empty directory (no .dat files)
3. **PNG Fallback** - Only covers surface (Y < 5860)

For underground areas like the Dwarven Mine (Y=9757):
- PNG calculates `imageY = 5860 - 9757 = -3897` (out of bounds)
- Out-of-bounds returns `true` ("optimistically walkable")
- A* computes fake path straight through cave walls
- Player tries to follow path → hits real walls → stuck

## Fix Applied

**File:** `manny_src/utility/PlayerHelpers.java` (line 1049-1092)

Modified `findPathGlobalAStar` to use RuneLite's collision API directly for short distances:

```java
if (distance <= 20)
{
    // Use LOCAL A* with RuneLite's collision API
    // Queries client.getCollisionMaps() directly - accurate for caves
    List<WorldPoint> localPath = findPathAStar(start, goal, 25);
    ...
}
```

| Distance | Method | Data Source |
|----------|--------|-------------|
| <= 20 tiles | Local A* | RuneLite collision API (accurate) |
| > 20 tiles | Global A* | Cached/PNG data (may have gaps) |

## Verification

Look for these logs when pathfinding in caves:
```
[Global A*] Distance 20 <= 20 tiles, using LOCAL collision API for accuracy
[Global A*] Local A* found path with N waypoints
```

## Original Symptoms
1. **"Player stuck - no movement"** error displayed in navigation overlay
2. Navigation computes a path (shows waypoints 1, 2, 3) but player doesn't actually move
3. Nav Time keeps increasing (40s, 100s+) without progress toward destination
4. Efficiency shows 0.00x (zero progress)

## Original Reproduction
- Location: Dwarven Mine (underground at ~3045, 9757)
- Target: Iron rocks at (3033, 9737)
- Distance: ~20 tiles
- Result: Path computed but player remains stationary

## Remaining Limitations

- Paths > 20 tiles in underground areas may still have issues
- Long-distance underground navigation should use waypoints through visited areas
- For very long underground paths, consider breaking into < 20 tile segments

## Workaround (if issue persists)
- Use `INTERACT_OBJECT Iron_rocks Mine` directly instead of GOTO + POWER_MINE
- Player will auto-walk to reachable objects
- Use shorter GOTO distances (break path into segments)
