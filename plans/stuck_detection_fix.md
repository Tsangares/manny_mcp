# Fix Plan: Forever Clicking / Unreachable Target Issue

## Root Cause Analysis

**What happened:** POWER_MINE selected an iron rock behind a wall. The navigation system tried to reach an adjacent tile, but that tile was also blocked/unreachable. The bot oscillated between nearby tiles indefinitely, never recognizing it couldn't reach the target.

**Contributing factors:**
1. **No reachability validation** - `findAvailableRocks()` returns ALL rocks within 15 tiles, including those behind walls
2. **Adjacent tile selection ignores walkability** - Lines 19595-19613 pick the "closest" adjacent tile without checking if it's actually walkable
3. **No stuck detection** - No timeout on "oscillation patterns" where position changes but goal is never reached
4. **Inventory items break drop routine** - Beer/Kebab from random player donations prevented iron ore from being dropped

## The Oscillation Pattern

```
Position log (last 40 seconds):
  (3039, 9776) → (3038, 9775) → (3037, 9775) → (3038, 9775) → (3039, 9776) → ...
```

Bot kept trying different approach angles but could never actually reach the rock.

## Fix Plan

### Fix 1: Reachability Check for Rocks (HIGH PRIORITY)

**File:** `PlayerHelpers.java` - `findAvailableRocks()` (~line 28519)

Before returning rocks, filter out unreachable ones:
```java
// Filter rocks that have at least one walkable adjacent tile
rocks = rocks.stream()
    .filter(rock -> hasWalkableAdjacentTile(rock.getWorldLocation()))
    .collect(Collectors.toList());
```

New helper method:
```java
private boolean hasWalkableAdjacentTile(WorldPoint location) {
    WorldPoint[] adjacent = new WorldPoint[] {
        new WorldPoint(location.getX(), location.getY() - 1, location.getPlane()),
        new WorldPoint(location.getX() - 1, location.getY(), location.getPlane()),
        new WorldPoint(location.getX() + 1, location.getY(), location.getPlane()),
        new WorldPoint(location.getX(), location.getY() + 1, location.getPlane())
    };

    for (WorldPoint adj : adjacent) {
        if (isWalkable(adj)) return true;
    }
    return false;
}
```

### Fix 2: Stuck Detection with Oscillation Pattern (HIGH PRIORITY)

**File:** `PlayerHelpers.java` - `handlePowerMine()` (~line 19497)

Add oscillation detection:
```java
// Track recent positions (ring buffer of last 10)
Queue<WorldPoint> recentPositions = new LinkedList<>();
int oscillationThreshold = 5; // If we visit same tile 5+ times in last 10 moves, we're stuck

// In the mining loop, after each movement attempt:
WorldPoint currentPos = client.getLocalPlayer().getWorldLocation();
recentPositions.add(currentPos);
if (recentPositions.size() > 10) recentPositions.poll();

// Check for oscillation
Map<WorldPoint, Long> positionCounts = recentPositions.stream()
    .collect(Collectors.groupingBy(p -> p, Collectors.counting()));

boolean isOscillating = positionCounts.values().stream()
    .anyMatch(count -> count >= oscillationThreshold);

if (isOscillating) {
    log.warn("[POWER_MINE] Detected oscillation pattern - marking rock as unreachable");
    unreachableRocks.add(targetRock.getWorldLocation());
    lastMinedRock = targetRock;
    continue; // Try different rock
}
```

### Fix 3: Global Navigation Timeout (MEDIUM PRIORITY)

**File:** `PlayerHelpers.java` - `gotoPositionSafe()`

Add a timeout for navigation attempts:
```java
long navStartTime = System.currentTimeMillis();
int maxNavTimeMs = 30000; // 30 second max to reach any destination

// In navigation loop:
if (System.currentTimeMillis() - navStartTime > maxNavTimeMs) {
    log.warn("[NAV] Navigation timeout - destination may be unreachable");
    return false; // Signal failure to caller
}
```

### Fix 4: Smarter Drop Routine (LOW PRIORITY)

**File:** `MiningHelper.java` or relevant drop handler

When dropping, drop ALL droppable items, not just expected ore:
```java
// Instead of: dropAll("Iron ore")
// Use: dropAllExcept(PROTECTED_ITEMS) // e.g., pickaxe, runes
```

## Implementation Order

1. **Fix 2 (Stuck Detection)** - Fastest to implement, immediately prevents infinite loops
2. **Fix 1 (Reachability Check)** - Prevents selecting bad targets in the first place
3. **Fix 3 (Nav Timeout)** - Safety net for navigation
4. **Fix 4 (Smart Drop)** - Nice to have, prevents inventory lock issues

## Testing

After implementing:
1. Start POWER_MINE in Shilo Village gem mine (where the bug occurred)
2. Verify rocks behind walls are NOT selected
3. Intentionally place a bad rock in the list, verify oscillation detection kicks in
4. Verify timeout triggers if pathfinder can't reach destination

## Metrics to Add

```java
// Track for monitoring
int rocksSkippedUnreachable = 0;
int oscillationDetections = 0;
int navTimeouts = 0;

// Log periodically
log.info("[POWER_MINE] Stats: {} rocks skipped (unreachable), {} oscillation detections, {} nav timeouts",
    rocksSkippedUnreachable, oscillationDetections, navTimeouts);
```
