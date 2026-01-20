# Combat Targeting & Camera Improvements

**Date:** 2026-01-19
**Location:** Hill Giants, Edgeville Dungeon
**Account:** main (ArmAndALegs)

## Summary

Implemented combat targeting improvements for singles combat zones and made camera pitch configurable to prevent combat system from overriding user preferences.

## Changes Made

### 1. Combat Aggro-Stolen Detection

**Problem:** When another player steals your target mid-fight, the bot would wait until timeout instead of finding a new target.

**Solution:** Added `DeathWaitResult` enum to distinguish between:
- `DIED` - NPC died, continue looting
- `AGGRO_STOLEN` - Another player took target, immediately find new NPC
- `STUCK` - Combat not progressing, retry or fail

**Files Modified:**
- `manny_src/utility/CombatSystem.java` (lines 112-146, 770-795, 1159-1170, 1197-1234)
- `manny_src/utility/PlayerHelpers.java` (lines 17822-17828, 17872-17878)

**Key Code:**
```java
// In waitForNPCDeath():
if (snapshot.npcTargetingOther) {
    log.info("[COMBAT-RELEASE] NPC switched target to '{}' - releasing", snapshot.npcTargetName);
    return DeathWaitResult.aggroStolen();
}

// In kill loop:
if (result.isAggroStolen()) {
    log.info("[AGGRO-STOLEN] Another player took our target - immediately finding new NPC");
    Thread.sleep(200);
    continue;  // Find new target without counting as failure
}
```

### 2. NPC Priority Selection

**Problem:** Bot would click any available NPC even if one was already attacking the player.

**Solution:** Added priority loop before LOS check - if an NPC is already attacking us, select that one first.

**File:** `manny_src/utility/PlayerHelpers.java` (lines 17639-17662)

```java
// PRIORITY: Check if any NPC is already attacking us (they get priority in singles)
for (NPC candidate : candidates) {
    Actor interacting = helper.readFromClient(() -> candidate.getInteracting());
    if (interacting != null) {
        boolean isFightingUs = helper.readFromClient(() -> {
            Player me = client.getLocalPlayer();
            return me != null && interacting.equals(me);
        });
        if (isFightingUs) {
            log.info("Prioritizing NPC already attacking us at distance {}", dist);
            target = candidate;
            break;
        }
    }
}
```

### 3. Configurable Camera Stabilization

**Problem:** Combat system would override user's camera pitch setting every click.

**Solution:**
1. Made `stabilize_camera` MCP tool accept `pitch` and `zoom_in_scrolls` parameters
2. Modified combat to only adjust pitch if below minimum threshold (350)
3. Added `targetPitch < 0` handling to skip pitch adjustment entirely

**Files Modified:**
- `manny_src/utility/commands/CameraStabilizeCommand.java`
- `manny_src/utility/CameraSystem.java` (lines 2111-2149, 1146-1170)
- `manny_src/utility/CombatSystem.java` (lines 853-878)
- `mcptools/tools/commands.py` (lines 605-663)

**Usage:**
```python
# Max top-down for dungeons
stabilize_camera(pitch=512)

# Default
stabilize_camera()  # pitch=400, zoom=8

# Custom
stabilize_camera(pitch=300, zoom_in_scrolls=10)
```

**Pitch Values:**
- 128 = level (looking straight ahead)
- 256 = slight top-down
- 400 = default top-down
- 512 = maximum top-down (best for dungeons)

## XP Rates Observed

Training at Hill Giants with 48 Attack, 55 Strength:

| Metric | Value |
|--------|-------|
| Attack XP/hr | ~14,000-15,000 |
| Hitpoints XP/hr | ~4,500-5,000 |
| Prayer XP/hr | ~1,200-1,300 |
| Total Combat XP/hr | ~20,000 |

## F2P Training Progression

| Stats | Best Location |
|-------|---------------|
| 45-60 atk/str | Hill Giants |
| 60-70 atk/str | Moss Giants (about equal) |
| 70+ atk/str | Ogresses (Corsair Cove) |

Note: Slayer is **members only** - not available in F2P.

## Log Messages to Watch

- `[COMBAT-RELEASE]` - NPC switched to another player
- `[AGGRO-STOLEN]` - Immediately finding new target
- `Prioritizing NPC already attacking us` - Priority selection working
- `Skipping pitch adjustment` - Camera respecting user setting

## Known Issues

- Camera pitch control has some drift (game engine limitation)
- Requested 512 pitch may result in actual ~250-350
- This is acceptable - the important thing is combat no longer overrides it

## Session Stats

- Started: ~11:00 PST
- Level ups during session:
  - Attack: 45 → 48
  - Hitpoints: 52 → 53
  - Prayer: 31 → 32
