# FISH_DRAYNOR_LOOP: Banking fails due to location detection overlap

**Status:** Open
**Priority:** High
**File:** `manny/utility/commands/FishDraynorLoopCommand.java`
**Date:** 2026-01-25

## Summary

The `FISH_DRAYNOR_LOOP` command gets stuck after fishing completes. The player walks toward the bank but never opens it or deposits fish, causing an infinite loop.

## Root Cause

In `detectFishingLocation()` (lines 287-292), location detection checks fishing spot distance **before** bank distance:

```java
if (distToFishingSpot <= 8) return FishingLocation.AT_FISHING_SPOT;  // Checked FIRST
if (distToBank <= 8) return FishingLocation.AT_BANK;
```

The fishing spot `(3086, 3231)` and bank `(3091, 3243)` are only 12 tiles apart. With an 8-tile detection radius for each, there's a 4-tile **overlap zone**.

When player ends up at position like `(3090, 3239)`:
- Distance to fishing spot: **8 tiles** (Chebyshev)
- Distance to bank: **4 tiles** (Chebyshev)

Player is **closer to the bank** but gets classified as `AT_FISHING_SPOT` because that check comes first.

### The Infinite Loop

1. Player at bank area with full inventory
2. Incorrectly detected as `AT_FISHING_SPOT`
3. State machine: "inventory full at fishing spot -> go to bank"
4. `GOTO` completes immediately (already there)
5. Still detected as `AT_FISHING_SPOT`
6. Repeat forever

## Fix

Check which location is closer when in the overlap zone:

```java
if (distToFishingSpot <= 8 && distToBank <= 8) {
    // In overlap zone - use the closer one
    return distToBank < distToFishingSpot ? FishingLocation.AT_BANK : FishingLocation.AT_FISHING_SPOT;
}
if (distToFishingSpot <= 8) return FishingLocation.AT_FISHING_SPOT;
if (distToBank <= 8) return FishingLocation.AT_BANK;
return FishingLocation.ELSEWHERE;
```

**Note:** Fix already written to source file at `/home/wil/desktop/manny/manny/utility/commands/FishDraynorLoopCommand.java` - needs rebuild.

## Steps to Reproduce

1. Run `FISH_DRAYNOR_LOOP 150`
2. Wait for inventory to fill (~5 min)
3. Player walks toward bank but stops ~4 tiles away
4. Player stands idle with full inventory indefinitely
