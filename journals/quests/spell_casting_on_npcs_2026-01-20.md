# Spell Casting on NPCs - Lessons Learned
**Date:** 2026-01-20

## The Problem

Casting Wind Strike on a chicken during Tutorial Island (Magic section) failed repeatedly. The `CAST_SPELL_NPC Wind_Strike Chicken` command reports "NPC not found" even though chickens are clearly visible and nearby (4-7 tiles away according to game state).

## Root Cause

**Deadlock in `handleCastSpellNPC`** - The implementation at `PlayerHelpers.java:12090-12327` has a critical threading bug:

```java
// Line 12123: Command runs on background executor
executors.getBackgroundExecutor().submit(() -> {
    // ...
    // Line 12249: Already on client thread via invokeLater
    clientThread.invokeLater(() -> {
        // Line 12252: BUG - gameHelpers.getNPC() internally calls
        // helper.readFromClient() which WAITS for client thread
        // = DEADLOCK (waiting for the thread we're already on)
        npcHolder[0] = gameHelpers.getNPC(npcName);
    });
});
```

The `gameHelpers.getNPC()` method (GameEngine.java:1148) uses `helper.readFromClient()` internally, which blocks waiting for the client thread. But we're already executing on the client thread via `invokeLater`, so it deadlocks or times out.

## Key Lessons

### 1. Client Thread Access Must Not Nest readFromClient Calls

**What happened:** Code inside `clientThread.invokeLater()` called a helper that itself uses `readFromClient()`, causing deadlock.

**Why:** `readFromClient()` blocks waiting for client thread. If you're already on client thread, you wait forever.

**Solution:**
```java
// BAD - deadlock
clientThread.invokeLater(() -> {
    NPC npc = gameHelpers.getNPC(npcName);  // readFromClient inside!
});

// GOOD - direct access when already on client thread
clientThread.invokeLater(() -> {
    List<NPC> npcs = client.getNpcs();
    NPC npc = npcs.stream()
        .filter(n -> n.getName() != null && n.getName().equalsIgnoreCase(npcName))
        .findFirst()
        .orElse(null);
});
```

### 2. Working Pattern for Spell Casting (Workaround)

**What happened:** The workaround that actually worked for casting Wind Strike on a chicken:

**Steps:**
```python
# 1. Click spell widget directly (Wind Strike = 14286856)
click_widget(widget_id=14286856)
# Wait for spell to be selected (cursor changes)
time.sleep(1.5)

# 2. Move mouse to NPC area on screen
send_command("MOUSE_MOVE 300 240")  # Approximate chicken position
time.sleep(0.5)

# 3. Click to cast
send_command("MOUSE_CLICK left")
```

**Why it works:** Bypasses the broken command entirely. Uses widget clicking (reliable) + coordinate click (unreliable but worked).

**Caveat:** Coordinates are camera-dependent and "got lucky" - needs a better solution.

### 3. Need CLICK_NPC Command

**What happened:** No command exists to simply click on an NPC's convex hull without action filtering.

**Why needed:** When a spell is selected, clicking on NPC should cast the spell. The existing `INTERACT_NPC` filters by action (like "Attack" or "Talk-to"), which doesn't work for spell casting context.

**Proposed command:**
```
CLICK_NPC <npc_name>
```
- Finds NPC by name only (no action filter)
- Clicks on NPC's convex hull center
- Returns success/failure
- Used after selecting a spell to complete the cast

## Anti-Patterns

1. **Don't** use `gameHelpers.getNPC()` inside `clientThread.invokeLater()` blocks - causes deadlock
2. ~~**Don't** assume `CAST_SPELL_NPC` works - it's fundamentally broken due to threading~~ **FIXED** - now uses thread-safe findNPCByNamePublic
3. **Don't** rely on exact coordinates for NPC clicking - use `CLICK_NPC <npc_name>` instead

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_game_state(fields=["nearby"])` | See all NPCs with distances |
| `get_logs(grep="CAST_SPELL", level="ALL")` | See where spell casting fails |
| `query_nearby(include_npcs=True)` | Quick NPC discovery |

## Interface Gaps Identified

- [x] **Plugin needs:** Fix CAST_SPELL_NPC threading deadlock - **FIXED** (2026-01-20)
- [x] **Plugin needs:** New `CLICK_NPC` command that clicks NPC convex hull without action filtering - **IMPLEMENTED** (2026-01-20)
- [x] **Plugin needs:** Alternative spell casting approach using `interactionSystem.clickNPCSafe()` pattern - **Done via CLICK_NPC**

## Proposed Fixes

### Option A: Fix CAST_SPELL_NPC (Recommended)

Replace lines 12246-12267 in PlayerHelpers.java:
```java
// CURRENT (broken):
clientThread.invokeLater(() -> {
    npcHolder[0] = gameHelpers.getNPC(npcName);  // deadlock!
});

// FIXED:
clientThread.invokeLater(() -> {
    List<NPC> npcs = client.getNpcs();
    npcHolder[0] = npcs.stream()
        .filter(n -> n.getName() != null &&
                     n.getName().toLowerCase().contains(npcName.toLowerCase()))
        .min((a, b) -> {
            WorldPoint p = client.getLocalPlayer().getWorldLocation();
            int distA = a.getWorldLocation().distanceTo(p);
            int distB = b.getWorldLocation().distanceTo(p);
            return Integer.compare(distA, distB);
        })
        .orElse(null);
});
```

### Option B: Add CLICK_NPC Command (Also Needed)

Create new command in PlayerHelpers.java that:
1. Uses `InteractionSystem.findNPCByName()` (no action filter)
2. Uses `InteractionSystem.clickNPCSafe()` pattern to click convex hull
3. Returns success/failure

Handler format:
```java
case "CLICK_NPC":
    return handleClickNPC(parts.length > 1 ? parts[1] : "");
```

## Key Widget IDs for Spell Casting

| Spell | Widget ID | Notes |
|-------|-----------|-------|
| Wind Strike | 14286856 | Basic combat spell, used in Tutorial Island |
| Home Teleport | 14286848 | Has 30-min cooldown |

## Files Modified

| File | Change |
|------|--------|
| `utility/PlayerHelpers.java:10011` | Added CLICK_NPC switch case |
| `utility/PlayerHelpers.java:12247-12271` | Fixed CAST_SPELL_NPC to use findNPCByNamePublic instead of deadlocking gameHelpers.getNPC() |
| `utility/PlayerHelpers.java:12354-12431` | Added handleClickNPC handler |
| `utility/InteractionSystem.java:1078-1092` | Added public findNPCByNamePublic wrapper |

## Time Lost to Issue

| Issue | Time Lost | Status |
|-------|-----------|--------|
| CAST_SPELL_NPC deadlock debugging | ~40 min | **FIXED** |
| Finding workaround (manual clicking) | ~20 min | WORKAROUND WORKS |

## Summary

The spell casting command has a threading deadlock. A working workaround exists using widget clicks + coordinate mouse moves, but it's unreliable. Two fixes are needed:
1. Fix the deadlock in CAST_SPELL_NPC (direct client.getNpcs() access)
2. Add CLICK_NPC command for simpler spell-on-NPC targeting
