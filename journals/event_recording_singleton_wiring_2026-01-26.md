# Event Recording System - Singleton Wiring Lessons
**Date:** 2026-01-26

## The Problem

Event recording for routine generation was implemented in the MCP (Python) side with `get_event_history` and `generate_routine` tools, but the Java plugin side wasn't actually recording events. When I added the recording hooks, interactions were being recorded inconsistently - working initially, then stopping after restarts.

## Root Cause

**Guice dependency injection without `@Singleton` creates multiple instances.**

The `InteractionSystem` class was injected into both `MannyPlugin` and `PlayerHelpers`. Without `@Singleton`, Guice created TWO separate instances:
1. MannyPlugin's instance - received `locationHistory` wiring in `startUp()`
2. PlayerHelpers' instance - used for actual command execution, but `locationHistory` was NULL

The wiring log showed success because MannyPlugin's instance got wired, but commands used PlayerHelpers' instance which never received the wiring.

## Key Lessons

### 1. Always Use @Singleton for Shared State Classes

**What happened:** `InteractionSystem` had a `locationHistory` field that needed to be wired once and used everywhere.

**Why:** Without `@Singleton`, Guice creates a new instance for each `@Inject` site. Any state set on one instance doesn't affect others.

**Solution:**
```java
// BAD - Multiple instances, state not shared
@Slf4j
public class InteractionSystem {
    private GameEngine.LocationHistory locationHistory;  // NULL in other instances!
}

// GOOD - Single instance shared everywhere
@Slf4j
@Singleton
public class InteractionSystem {
    private GameEngine.LocationHistory locationHistory;  // Set once, used everywhere
}
```

### 2. Debug Wiring Issues with Instance Identity Logs

**What happened:** "LocationHistory wired to InteractionSystem" logged successfully, but events weren't recorded.

**Why:** The log came from one instance, commands used another.

**Solution:**
```java
// Add debug logging INSIDE the method that needs the wired dependency
if (locationHistory != null) {
    // ... use it
} else {
    log.warn("[EVENT-DEBUG] locationHistory is NULL - wiring failed!");
}

// Or log identity to verify same instance:
log.info("InteractionSystem instance: {}", System.identityHashCode(this));
```

### 3. Event Recording Hooks Must Cover All Code Paths

**What happened:** Added event recording to `interactWithGameObject(int objectId, ...)` but commands used `interactWithGameObject(String objectName, ...)` which had a completely different implementation.

**Why:** Method overloads can have independent implementations. The string-based method found objects itself and called `clickGameObjectSafe` directly, bypassing the hook.

**Solution:** Trace the actual call path from command handler:
```
INTERACT_OBJECT command
  → handleInteractObject()
  → interactionSystem.interactWithGameObject(name, action)  // 2-param
  → interactWithGameObject(name, action, 15, 3)             // 4-param - DIFFERENT method!
```

Add hooks to ALL methods that can succeed, not just one overload.

### 4. TileObjects vs GameObjects Have Separate Paths

**What happened:** Recording worked for regular objects but not for doors/gates.

**Why:** Doors, gates, and fences are often `WallObject` (a `TileObject`), not `GameObject`. The code has two separate success branches:
1. `clickGameObjectSafe()` success → record event
2. `clickTileObjectSafe()` success → also needs recording!

**Solution:** Add recording to BOTH paths:
```java
// GameObject path (line ~230)
if (clickGameObjectSafe(...)) {
    if (locationHistory != null) {
        locationHistory.recordInteraction(...);
    }
    return true;
}

// TileObject path (line ~300)
if (clickTileObjectSafe(...)) {
    if (locationHistory != null) {
        locationHistory.recordDoor(...);  // Different method for doors
    }
    return true;
}
```

## Anti-Patterns

1. **Don't** assume wiring logs prove the right instance is wired - verify at usage site
2. **Don't** add hooks to just one method overload - trace the actual call path
3. **Don't** forget TileObject interactions (doors, gates) need separate handling from GameObjects
4. **Don't** rely on log.debug for critical debugging - use log.info to ensure visibility

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `grep "EVENT-DEBUG" /tmp/runelite_*.log` | Verify locationHistory state at usage time |
| `grep "@Singleton" *.java` | Check if shared-state classes are singletons |
| `grep -n "interactWith" InteractionSystem.java` | Find all method overloads |
| `python3 -c "...json.load..." location_history.json` | Verify events are being written |

## Interface Gaps Identified

Events NOT currently recorded:
- [ ] Combat style changes (widget clicks)
- [ ] Inventory interactions (drop, equip via widget)

Events that ARE recorded (updated 2026-01-26):
- [x] INTERACT_NPC (Talk-to, Attack, etc.)
- [x] INTERACT_OBJECT (GameObjects)
- [x] INTERACT_OBJECT (TileObjects - doors, gates)
- [x] CLICK_DIALOGUE (all success paths)
- [x] USE_ITEM_ON_OBJECT
- [x] PICK_UP_ITEM
- [x] BANK_WITHDRAW
- [x] BANK_DEPOSIT_ITEM
- [x] BANK_DEPOSIT_ALL
- [x] BANK_DEPOSIT_EQUIPMENT

## Files Modified

| File | Change |
|------|--------|
| `InteractionSystem.java:4` | Added `import com.google.inject.Singleton` |
| `InteractionSystem.java:34` | Added `@Singleton` annotation |
| `InteractionSystem.java:230-243` | Added event recording for GameObject interactions |
| `InteractionSystem.java:305-317` | Added event recording for TileObject (door) interactions |
| `InteractionSystem.java:970` | Added debug logging for NPC interactions |
| `GameEngine.java:9910-10150` | Created LocationHistory class (prior session) |
| `PlayerHelpers.java:23343-23351` | Added event recording for BANK_DEPOSIT_ITEM |
| `PlayerHelpers.java:23619-23630` | Added event recording for BANK_WITHDRAW |
| `PlayerHelpers.java:23187-23195` | Added event recording for BANK_DEPOSIT_ALL |
| `PlayerHelpers.java:23234-23242` | Added event recording for BANK_DEPOSIT_EQUIPMENT |
| `PlayerHelpers.java:27871-27879` | Added event recording for CLICK_DIALOGUE (nested children path 1) |
| `PlayerHelpers.java:27916-27924` | Added event recording for CLICK_DIALOGUE (container children path) |
| `PlayerHelpers.java:27949-27957` | Added event recording for CLICK_DIALOGUE (nested children path 2) |

## Summary

The core lesson: **When using Guice DI for classes that hold state (like `locationHistory`), always add `@Singleton`**. Without it, wiring appears to work but the wired instance isn't the one used for actual operations. Debug by logging at the exact point of use, not at the wiring point.
