# Phase 1 Navigation Infinite Clicking - Lessons Learned
**Date:** 2026-02-10

## The Problem

During superheat routine loop 5, GOTO fell back to Phase 1 "naive minimap clicking" and clicked south endlessly. The player walked from Falador to (2979, 3520) — hundreds of tiles in the wrong direction — with no timeout or abort.

## Root Cause

Phase 1 navigation in `PlayerHelpers.java` (lines ~3656-3969) had **no global timeout or iteration limit**. Its only exit conditions were:

1. **Reaching target** (`distance <= targetDistance`) — never happens if target is unreachable or the player is walking the wrong way
2. **Stuck detection** (mean speed < threshold) — doesn't trigger when the player IS moving, just in the wrong direction
3. **Consecutive minimap failures** (15 max) — resets on every successful click, so one good click resets the counter

The other navigation methods already had proper limits:
- `simpleDirectionalNavigationMultiClick`: 30s timeout + 200 iterations + oscillation detection
- A* path following: 120s timeout + 500 iterations + stuck detection

Phase 1 was the only method without safety limits — a gap in the navigation defense-in-depth.

## Key Lessons

### 1. Every navigation fallback needs a hard ceiling

**What happened:** Phase 1 is already a last-resort fallback (A* failed or unavailable). But because it had no ceiling, a failure in the fallback became an infinite loop.

**Why:** The stuck detector checks movement speed, not direction. A player walking briskly southward at full speed passes the "is moving" check even though they're going the wrong way entirely.

**Solution:**
```java
// BAD - only exit via reaching target or getting stuck
while (distance > targetDistance) {
    // click minimap toward target
    // sleep 500ms
    // check if stuck (speed-based)
}

// GOOD - hard limits that always fire regardless of movement state
long phase1StartTime = System.currentTimeMillis();
final long MAX_PHASE1_NAV_TIME_MS = 60_000;
int phase1Iterations = 0;
final int MAX_PHASE1_ITERATIONS = 200;

while (distance > targetDistance) {
    if (System.currentTimeMillis() - phase1StartTime > MAX_PHASE1_NAV_TIME_MS) {
        log.error("[NAV-PHASE1] TIMEOUT - destination likely unreachable");
        return false;
    }
    if (++phase1Iterations > MAX_PHASE1_ITERATIONS) {
        log.error("[NAV-PHASE1] Exceeded iteration limit");
        return false;
    }
    // ... rest of loop
}
```

### 2. Speed-based stuck detection has a blind spot

**What happened:** The stuck detector measures if the player is moving. But "moving in the wrong direction" looks identical to "making progress" from a speed perspective.

**Why:** Minimap clicking translates a world-space vector to screen-space. If the coordinate conversion produces a valid minimap click (even slightly off-target), the player walks confidently in the wrong direction at full speed. Speed > 0, so stuck detector says "all good."

**Lesson:** Speed-based detection catches stationary stalls. Time/iteration limits catch directional failures. You need both.

### 3. Fallback methods need MORE safety, not less

Counterintuitively, Phase 1 (the fallback) had the fewest safety checks despite being the method most likely to fail. The primary methods (A*, directional nav) had timeouts, iteration limits, AND oscillation detection. The fallback that only runs when everything else failed had none.

**Pattern:** When adding fallback/retry logic, give it STRICTER limits than the primary path, not looser ones.

## Anti-Patterns

1. **Don't rely solely on stuck detection for navigation safety** - it can't detect directional errors, only stalls
2. **Don't assume fallback code runs rarely enough to skip safety limits** - when it runs, it's already in a degraded state and MORE likely to fail catastrophically
3. **Don't let counter-based limits reset on partial success** - the 15-consecutive-minimap-failures counter reset on every good click, making it useless for long wrong-direction walks

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="NAV-PHASE1")` | See which phase navigation used and if it timed out |
| `get_logs(grep="NAV-METHOD")` | See which navigation method was selected |
| `get_game_state(fields=["location"])` | Check if player drifted far from expected position |

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/PlayerHelpers.java` | Added 60s timeout + 200 iteration limit to Phase 1 navigation loop |
