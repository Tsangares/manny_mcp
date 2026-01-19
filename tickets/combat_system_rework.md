# Combat System Rework

## Status: Research/Planning

## Overview

The current combat system (KILL_LOOP, CombatSystem.java) works for basic combat but has significant issues with post-kill actions (looting, bone pickup, burying). This ticket documents observed problems and proposed improvements.

## Current Architecture

```
KILL_LOOP (PlayerHelpers.java ~line 17750)
    └── attackAndWaitForDeath()
            └── CombatSystem.attackNPC()
            └── CombatSystem.waitForNPCDeath()
                    └── Mid-combat eating (60% HP threshold)
    └── Post-kill loot pickup (lines 17806-17850)
    └── Post-kill bone handling (lines 17853-17871)
    └── Post-kill bone burying (lines 17873-17890)
```

## Observed Problems

### 0. Menu Verification Fails (ROOT CAUSE)

**This is likely the root cause of all other issues!**

**Symptom:** NPC marked as "visible" but mouse doesn't land on it:
```
INFO  - ✓ Fast path successful - NPC 'Hill Giant' visible immediately
ERROR - Menu verification failed - 'Attack' or 'Cast' option not found for 'Hill Giant'
INFO  - === Current Menu Entries (1 total) ===
INFO  -   [0] Option: 'Cancel' | Target: ''
```

**Root cause:** ConvexHull visibility check passes but Bezier mouse movement doesn't land on NPC hitbox. After 3 failed attempts, attack is abandoned.

**Why post-kill never runs:** Attack never succeeds → no kill → no loot section.

**Fix needed:**
- Better click validation with retry at different hull points
- Use `smartMoveToWidget` style verification for NPCs
- Or: simpler direct click without Bezier curves

### 1. Post-Kill Code Never Executes

**Symptom:** Combat works (NPC HP tracked, attacks land), but after kills:
- No "Picking up loot at death location" logs
- No "Picking up bones at death location" logs
- No "Burying bones from inventory" logs

**Hypothesis:** Either:
- `waitForNPCDeath()` never returns true (kill not detected)
- Exception thrown before reaching loot section
- Death location not captured correctly

**Investigation needed:**
- Add logging before/after `attackAndWaitForDeath()` call
- Verify return value flow
- Check if deathLocation is populated

### 2. Camera Visibility Issues

**Symptom:** "360° camera scan failed - NPC 'Hill Giant' could not be made visible!"

**Root cause:** `findNPCWithCameraAdjust()` tries static LOS check which fails underground.

**Current mitigation:** Code has underground detection but still fails intermittently.

### 3. NPC Position Null

**Symptom:** "NPC position is null" errors during combat targeting.

**Root cause:** NPC despawns or moves between detection and interaction.

**Needs:** Better null checking and retry logic.

### 4. Loot Items Hardcoded

**Current:** Loot items hardcoded in KILL_LOOP:
```java
String[] valuableLoot = {"Law rune", "Limpwurt root", "Nature rune"};
```

**Should be:** Configurable via command args or routine YAML.

### 5. No Fire/Water Rune Pickup

User requested: "Pick up any Law Fire Water runes"
Currently only picks up: Law rune, Limpwurt root, Nature rune

### 6. STUCK_NO_ANIMATION False Positives

**Symptom:** Combat aborts with "STUCK_NO_ANIMATION" even though NPC HP is dropping.

**Root cause:** When another player is also attacking the same NPC, our player's animation may pause while the NPC is being hit. The stuck detection sees no animation for 5+ seconds and aborts.

**Logs:**
```
elapsed=4320ms anim=-1 hp=23/30 dist=2 retaliation=false status=PROGRESSING
[COMBAT-STUCK] Combat not progressing: STUCK_NO_ANIMATION after 5182ms
Aborting combat due to stuck state: STUCK_NO_ANIMATION
```

**Fix:** Consider HP changes as combat progress, not just player animation.

### 7. Player Null During Camera Scan

**Symptom:**
```
[Before 360° scan] Cannot diagnose NPC - player is null
Cannot scan for NPC 'null' - position is null
```

**Root cause:** Race condition - NPC reference becomes stale between visibility check and camera scan.

**Fix:** Better null handling, re-fetch NPC if stale.

### 8. HP -1/-1 Early in Combat

**Symptom:** Health bars show -1/-1 for first few seconds:
```
[COMBAT-PROGRESS] elapsed=1058ms anim=-1 hp=-1/-1 dist=1 retaliation=false
```

**Root cause:** NPC health bar hasn't loaded yet from server.

**Impact:** Can't track damage progress early. Not critical but confusing in logs.

## Proposed Improvements

### Phase 1: Fix Post-Kill Detection

1. Add detailed logging around kill completion
2. Verify `waitForNPCDeath()` return value
3. Ensure death location captured before NPC despawns
4. Add fallback: if no death location, use player's current location

### Phase 2: Configurable Loot

```
KILL_LOOP <npc_name> <count> [loot:item1,item2,item3]
```

Or read from routine YAML:
```yaml
loot_items:
  - "Law rune"
  - "Fire rune"
  - "Water rune"
  - "Big bones"
```

### Phase 3: Better Camera Handling

- Skip camera adjustment for underground areas entirely
- Use different NPC finding strategy for dungeons
- Trust that nearby NPCs are interactable without LOS check

### Phase 4: Robust Death Detection

Current `waitForNPCDeath()` relies on:
- NPC HP reaching 0
- NPC despawning
- Combat state changing

Add fallback detection:
- XP drop received
- Combat animation ended
- Player no longer in combat after X seconds

### Phase 5: Ground Item Improvements

Current `PICK_UP_ITEM` issues:
- ~~Underscore conversion~~ (FIXED)
- Only picks up first matching item
- No priority system
- Doesn't handle stackable items well

Improvements:
- Pick up all matching items in area
- Priority queue (runes > bones > herbs)
- Smart stacking detection

## Testing Checklist

- [ ] Verify kill detection logs appear
- [ ] Confirm loot pickup triggers after kill
- [ ] Test bone pickup and burying
- [ ] Test with Fire/Water runes in loot list
- [ ] Verify camera doesn't break in dungeon
- [ ] Test low-food escape mechanism

## Related Files

- `manny_src/utility/PlayerHelpers.java` - KILL_LOOP handler (lines 17750-17900)
- `manny_src/utility/CombatSystem.java` - Core combat logic
- `manny_src/utility/InteractionSystem.java` - NPC/object interactions
- `/home/wil/manny-mcp/routines/combat/hill_giants_loot.yaml` - Example routine

## Session Notes

**2026-01-18:**
- KILL_LOOP runs, combat works, but post-kill section never reached
- Fixed PICK_UP_ITEM underscore conversion
- Fixed BURY_ALL to find "Big bones" not just "Bones"
- Neither fix helped because the code path never executes
- Need to trace execution flow from kill completion to loot pickup
