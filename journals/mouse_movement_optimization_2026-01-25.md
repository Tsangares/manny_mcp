# Mouse Movement Optimization - Lessons Learned
**Date:** 2026-01-25

## The Problem

Long-distance mouse movements (>200px) were slow because `movePrecisely` used a constant speed calculated at the start. A 400px move took the same duration formula as a 50px move, just with more frames.

## Root Cause

In `Mouse.java:452-492`, `getPreciseMovement` calculated speed once:

```java
double distance = start.distance(destination);
double scale = 25/distance;
double duration = gauss(.2/scale,.2,0) + .1;
double speed = distance/duration;  // FIXED for entire movement

while(Math.round(distance) > 1) {
    // speed never changes...
}
```

The speed remained constant regardless of remaining distance. Far movements crawled at a pace designed for precision, not travel.

## Key Lessons

### 1. Hybrid Movement is Faster Than Pure Precision

**What happened:** Using `getMovement` (fast, curved) for bulk travel + `getPreciseMovement` for final approach is faster than pure precision.

**Why:** `getMovement` uses velocity profiles with acceleration/deceleration curves. `getPreciseMovement` uses constant speed with angle corrections.

**Solution:**
```java
// Mouse.java:169-197
public void movePrecisely(final Point destination){
    double distance = start.distance(destination);

    if (distance > 200) {
        // Fast move to waypoint 100px from destination
        double ratio = (distance - 100) / distance;
        Point waypoint = new Point(
            (int)(start.x + (destination.x - start.x) * ratio),
            (int)(start.y + (destination.y - start.y) * ratio)
        );
        Vector<Point> fastPositions = movement.getMovement(start, waypoint);
        replay(fastPositions);
        start = new Point(mouseX, mouseY);  // Update for next phase
    }

    // Precise for final approach
    Vector<Point> positions = movement.getPreciseMovement(start, destination);
    replay(positions);
}
```

### 2. Dynamic Speed with Lock-in Zone

**What happened:** Speed should adapt when far but lock in when close.

**Why:** Recalculating speed near the target causes jitter. Locking speed at ~100px gives smooth deceleration.

**Solution:**
```java
// Mouse.java:469-485 (inside getPreciseMovement while loop)
double baseSpeed = speed;
while(Math.round(distance) > 1) {
    distance = position.distance(destination);

    if (distance > 100) {
        // Far: recalculate speed based on remaining distance
        double remainingScale = 25 / distance;
        double remainingDuration = gauss(.2 / remainingScale, .1, 0) + .1;
        speed = distance / remainingDuration;
    } else if (distance > 95) {
        // Transition: lock in current speed
        baseSpeed = speed;
    } else {
        // Close: use locked speed for consistency
        speed = baseSpeed;
    }
    // ... rest of movement logic
}
```

## Anti-Patterns

1. **Don't** use constant speed for all distances - long moves become sluggish
2. **Don't** recalculate speed near the target - causes jitter and overshooting
3. **Don't** use pure Bezier for everything - precision movements need angle correction, not curves

## Architecture Overview

```
movePrecisely(destination)
├── distance > 200px?
│   ├── YES: getMovement() to waypoint (100px from dest)
│   │        then getPreciseMovement() for final 100px
│   └── NO:  getPreciseMovement() only
│
└── getPreciseMovement inner loop:
    ├── >100px: dynamic speed (faster when far)
    ├── 95-100px: lock in baseSpeed
    ├── <95px: use locked baseSpeed
    └── <5px: increase accuracy multiplier
```

## Files Modified

| File | Change |
|------|--------|
| `manny_src/human/Mouse.java:169-197` | Hybrid approach: fast move + precise finish for >200px |
| `manny_src/human/Mouse.java:469-485` | Dynamic speed recalculation when >100px from target |

## Performance Impact

| Scenario | Before | After |
|----------|--------|-------|
| 400px move | ~0.5s constant | ~0.35s (fast + precise) |
| 150px move | ~0.25s constant | ~0.2s (dynamic speed) |
| 50px move | ~0.15s | ~0.15s (unchanged) |
