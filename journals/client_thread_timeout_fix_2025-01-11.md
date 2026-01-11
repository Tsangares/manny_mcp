# Client Thread Timeout - Why Long-Running Routines Freeze
**Date:** 2025-01-11

## The Problem

During extended fishing sessions (~5-6 trips), the RuneLite client would freeze completely. Commands stopped executing, the state file stopped updating, and the only recovery was a full client restart. This happened consistently after 20-40 minutes of operation.

## Root Cause

**The `readFromClient()` method in `ClientThreadHelper.java` uses a single 5-second timeout with no retry.** When the client thread is busy (loading screens, heavy rendering, garbage collection), the latch times out and throws a `RuntimeException` that cascades up and kills the entire command.

```java
// The problematic code (ClientThreadHelper.java:129-137)
boolean completed = latch.await(5, TimeUnit.SECONDS);
if (!completed) {
    // This exception crashes the entire command chain
    throw new RuntimeException("Client thread timeout after 5000ms - client thread may be blocked");
}
```

**Key insight:** The client thread handles ALL rendering. When it's busy with:
- Loading new map regions (e.g., ferry travel to Karamja)
- Rendering many NPCs/objects
- JVM garbage collection pauses

...the `readFromClient()` calls queue up and timeout. Once one fails, the exception propagates and leaves the plugin in a broken state.

## Key Lessons

### 1. One Long Timeout Is Worse Than Multiple Short Ones

**What happened:** A single 5-second timeout gave no chance for recovery.

**Why:** The client thread might be busy for 3-4 seconds but free up. A single 5s timeout either succeeds or catastrophically fails.

**Solution:**
```java
// BAD - one 5s timeout, throws on failure
public <T> T readFromClient(Supplier<T> getter) {
    latch.await(5, TimeUnit.SECONDS);
    if (!completed) throw new RuntimeException("timeout");
}

// GOOD - 3 retries of 2s each, returns null on failure
public <T> T readFromClientWithRetry(Supplier<T> getter, int maxRetries) {
    for (int attempt = 1; attempt <= maxRetries; attempt++) {
        boolean completed = latch.await(2, TimeUnit.SECONDS);
        if (completed) return result;
        Thread.sleep(500); // Let client thread recover
    }
    return null; // Graceful degradation
}
```

### 2. Return Null Instead of Throwing on Timeout

**What happened:** The exception from `readFromClient()` propagated up through `CameraSystem` → `InteractionSystem` → `CommandProcessor` → entire command fails.

**Why:** Exception-based error handling is appropriate for programming errors, not for transient conditions like "client thread is temporarily busy."

**Solution:** Added `readFromClientSafe()` that catches timeout exceptions and returns null:
```java
public <T> T readFromClientSafe(Supplier<T> getter) {
    try {
        return readFromClient(getter);
    } catch (RuntimeException e) {
        if (e.getMessage().contains("timeout")) {
            return null; // Caller handles null
        }
        throw e;
    }
}
```

### 3. Callers Must Handle Null Gracefully

**What happened:** Even with safe methods, callers like `CameraSystem.setCameraPitchSmooth()` would NPE on null.

**Solution:** Check for null and skip non-critical operations:
```java
// BAD - NPE if timeout
int currentPitch = helper.readFromClient(() -> client.getCameraPitch());

// GOOD - graceful skip
Integer currentPitch = helper.readFromClientWithRetry(() -> client.getCameraPitch());
if (currentPitch == null) {
    log.warn("Could not read camera pitch, skipping adjustment");
    return; // Continue without crashing
}
```

### 4. The CAMERA_STABILIZE Command Is a Major Timeout Source

**What happened:** The fishing routine calls `CAMERA_STABILIZE` 4 times per loop. Each call does multiple `readFromClient()` calls for pitch reading/verification.

**Why:** Camera operations are non-essential - if they fail, fishing still works. But they were crashing the entire routine.

**Solution:** Made camera operations resilient:
- Use `readFromClientWithRetry()` for initial pitch read
- Use `readFromClientSafe()` for verification (log warning, don't crash)
- Skip adjustment if reads fail

## The Fix

### Files Modified

| File | Change |
|------|--------|
| `ClientThreadHelper.java` | Added `readFromClientWithRetry()` (3 retries, 2s each) and `readFromClientSafe()` (returns null) |
| `CameraSystem.java` | Use retry methods, handle null gracefully, skip on failure |
| `InteractionSystem.java` | Use `readFromClientWithRetry()` for NPC and GameObject searches |
| `fishing_karamja_lobster.yaml` | Extended waypoint timeout 30s→45s, deposit delay 2s→2.5s |

### New Methods in ClientThreadHelper

```java
// Retry with shorter timeouts - more resilient
public <T> T readFromClientWithRetry(Supplier<T> getter, int maxRetries)
public <T> T readFromClientWithRetry(Supplier<T> getter)  // default 3 retries

// Return null instead of throwing - for non-critical reads
public <T> T readFromClientSafe(Supplier<T> getter)
```

## Anti-Patterns to Avoid

1. **Don't use single long timeouts** - Use multiple short timeouts with retries
2. **Don't throw exceptions for transient conditions** - Return null/empty for "temporarily unavailable"
3. **Don't let non-critical operations crash critical flows** - Camera adjustment failing shouldn't stop fishing
4. **Don't ignore the 5-second timeout in logs** - "Client thread timeout" = investigate and fix

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(level="ERROR", grep="timeout")` | Find timeout occurrences |
| `is_alive()` | Quick check if plugin is frozen |
| `check_health()` | Detailed health including state file staleness |
| `find_blocking_patterns()` | Static analysis of potential blocking code |
| `get_blocking_trace()` | Runtime analysis (requires instrumentation) |

## Interface Gaps Identified

- [x] Plugin needs: Retry logic in ClientThreadHelper (FIXED)
- [x] Plugin needs: Graceful degradation in CameraSystem (FIXED)
- [x] Plugin needs: Resilient NPC/object finding in InteractionSystem (FIXED)
- [ ] MCP needs: Automatic routine retry on transient failures
- [ ] CLAUDE.md needs: Document the new retry methods

## Metrics

| Before | After |
|--------|-------|
| ~5-6 trips before freeze | TBD - needs testing |
| Exception crashes command chain | Null return, graceful skip |
| 5s single timeout | 3x 2s retries (6s total, more resilient) |

## Testing Checklist

- [x] Code compiles without errors
- [x] Anti-pattern check passes (warnings only, no errors)
- [ ] Run 10+ fishing trips without freeze
- [ ] Verify camera operations skip gracefully on timeout
- [ ] Verify NPC interactions retry successfully
