# Infinite Pathfinding Loop - Lessons Learned
**Date:** 2026-01-27

## The Problem

The bot enters an infinite loop trying to reach an unreachable target, clicking "Cancel" once per second indefinitely. This wasted 2+ hours of session time with zero progress. The player oscillates between tiles but never reaches the goal, and POWER_MINE never recovers.

## Root Cause

**Multiple layers of failure:**

1. **Oscillation detection isn't triggered** - The stuck detection in `simpleDirectionalNavigationMultiClick()` (lines 2810-2831) checks if `mean speed < 0.5`. But when oscillating between tiles 2+ apart, mean speed stays above threshold.

2. **Navigation timeout doesn't propagate** - The 15-second timeout in POWER_MINE marks rocks as unreachable, but the navigation loop at line 2792 (`while (distance > targetDistance)`) has NO global timeout.

3. **"Cancel" menu not treated as failure** - When clicking an unreachable world tile, the menu shows only "Cancel". The bot keeps clicking without recognizing this as a terminal failure state.

4. **No maximum iteration limit** - The navigation while-loop can run indefinitely as long as distance > targetDistance.

## Key Lessons

### 1. Oscillation Detection Must Check Tile Revisits, Not Just Speed

**What happened:** Player bounced between (3053, 9765) and (3053, 9763) repeatedly.
**Why:** Mean speed was ~2 tiles/iteration - well above the 0.5 threshold.
**Solution:**

```java
// BAD - speed-only detection misses oscillation
if (mean < 0.5) { return false; }

// GOOD - track unique tiles visited
Set<WorldPoint> recentTiles = new HashSet<>();
for (int i = Math.max(0, traveled.size() - 10); i < traveled.size(); i++) {
    recentTiles.add(positions.get(i));
}
if (recentTiles.size() <= 2 && traveled.size() >= 10) {
    log.error("[NAV] Oscillation detected - only {} unique tiles in last 10 moves", recentTiles.size());
    return false;
}
```

### 2. Navigation Needs a Hard Time Limit

**What happened:** The while-loop ran for 2+ hours.
**Why:** No time-based escape hatch.
**Solution:**

```java
// File: PlayerHelpers.java, simpleDirectionalNavigationMultiClick()
long navStartTime = System.currentTimeMillis();
final long MAX_NAV_TIME_MS = 30_000; // 30 second max

while (distance > targetDistance) {
    // CRITICAL: Time-based escape hatch
    if (System.currentTimeMillis() - navStartTime > MAX_NAV_TIME_MS) {
        log.error("[NAV-MULTI] TIMEOUT after {}ms - destination unreachable", MAX_NAV_TIME_MS);
        return false;
    }
    // ... rest of loop
}
```

### 3. "Cancel" Menu = Invalid Target

**What happened:** Logs show "Cancel" clicks 1/second for 2+ hours.
**Why:** No code checks if menu only contains "Cancel" during navigation.
**Solution:**

```java
// After clicking minimap, check if we got a valid action
if (isMenuOnlyCancel()) {
    consecutiveCancelClicks++;
    if (consecutiveCancelClicks >= 5) {
        log.error("[NAV] 5 consecutive Cancel-only clicks - target unreachable");
        return false;
    }
} else {
    consecutiveCancelClicks = 0;
}
```

### 4. Maximum Iteration Count as Final Safety Net

**What happened:** Loop ran millions of iterations.
**Why:** While condition always true (distance never reaches 0 for unreachable target).
**Solution:**

```java
int iterations = 0;
final int MAX_ITERATIONS = 200; // Even slow pathing shouldn't need 200 clicks

while (distance > targetDistance) {
    if (++iterations > MAX_ITERATIONS) {
        log.error("[NAV-MULTI] Exceeded {} iterations - aborting", MAX_ITERATIONS);
        return false;
    }
    // ...
}
```

## Anti-Patterns

1. **Don't** use speed-only stuck detection - oscillation maintains average speed
2. **Don't** allow unbounded while-loops in navigation - always add time/iteration limits
3. **Don't** ignore "Cancel" menu responses - they indicate invalid targets
4. **Don't** rely solely on POWER_MINE timeout - lower-level navigation needs its own limits

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `tail -100 /tmp/runelite_main.log \| grep Cancel` | Detect infinite Cancel loops |
| `cat /tmp/manny_main_location_history.json \| jq '.positions[-20:]'` | Check for oscillation patterns |
| `grep "NAV-MULTI\|stuck" /tmp/runelite_main.log` | Find navigation failures |

## Interface Gaps Identified

- [x] Plugin needs: Time-based navigation timeout (30 seconds max)
- [x] Plugin needs: Iteration limit on navigation while-loops
- [x] Plugin needs: "Cancel" menu detection as failure condition
- [x] Plugin needs: Unique-tile oscillation detection (not just speed)
- [ ] MCP needs: Alert when state file shows player in same 5-tile area for 5+ minutes
- [ ] CLAUDE.md needs: Document that "Cancel" clicks indicate unreachable target

## Files to Modify

| File | Change |
|------|--------|
| `PlayerHelpers.java:2784` | Add timeout, iteration limit, Cancel detection to `simpleDirectionalNavigationMultiClick()` |
| `PlayerHelpers.java:2810` | Replace speed-only detection with oscillation detection |
