# Ground Item Spawns vs Ground Items - Lessons Learned
**Date:** 2026-01-24

## The Problem

When trying to pick up a small fishing net from a known spawn location in Lumbridge Swamp, `query_nearby(include_ground_items=True)` returned nothing despite being at the exact spawn coordinates. The item appeared invisible to the standard ground item query.

## Root Cause

**Static item spawns (like fishing nets near the Fishing tutor) are GameObjects, not TileItems (ground items).**

The OSRS game engine has two different systems:
1. **TileItems (Ground Items)** - Dropped items, loot, items that appeared dynamically
2. **GameObjects** - Static world objects, including permanent item spawns

The `query_nearby(include_ground_items=True)` only scans TileItems. The fishing net spawns are GameObjects with ID 674 that have a "Take" action.

## Session Walkthrough

### Phase 1: Research (WebFetch)

**Command:** `WebFetch(url="https://oldschool.runescape.wiki/w/Small_fishing_net", prompt="Find all F2P spawn locations...")`

**Why:** User requested F2P spawn locations. Wiki is authoritative source for OSRS data.

**Result:** Found 4 F2P locations - Lumbridge Swamp (2 spawns by Fishing tutor) was closest to current position.

### Phase 2: Initial Positioning

**Command:** `get_game_state(account_id="aux", fields=["location"])`

**Why:** Need to know current position before navigation.

**Result:** Position (3240, 3160, plane 0) - already near Lumbridge Swamp.

### Phase 3: Plugin Freeze Detection & Recovery

**Command:** `send_and_await(command="GOTO 3246 3157 0", await_condition="location:3246,3157")`

**Problem encountered:**
```json
{
  "success": false,
  "error": "Plugin appears frozen - state file is 81s stale",
  "diagnosis": "PLUGIN_FROZEN"
}
```

**Why this happened:** Client had been idle, plugin state file (`/tmp/manny_state.json`) wasn't being updated. State file is written every GameTick (~600ms), so >30s staleness indicates freeze.

**Recovery attempt 1:** `restart_if_frozen(account_id="aux")`
```json
{
  "success": false,
  "error": "Error during restart: 'MultiRuneLiteManager' object has no attribute 'stop'"
}
```
**Lesson:** MCP manager bug - `restart_if_frozen` calls an undefined method.

**Recovery attempt 2:** `stop_runelite(account_id="aux")`
```json
{
  "stopped": false,
  "message": "No instance for account: aux"
}
```
**Lesson:** Instance tracking was lost, possibly from previous crash.

**Recovery attempt 3:** `start_runelite(account_id="aux", display=":3")`
- Killed any orphan processes
- Started fresh client
- Waited for login via `await_state_change(condition="idle")`

**Verification:** `get_screenshot()` to visually confirm login screen → "Connecting to server..." → logged in.

### Phase 4: Navigation to Spawn

**Command:** `send_and_await(command="GOTO 3246 3157 0", await_condition="location:3246,3157", timeout_ms=15000)`

**Why:** Navigate to known fishing net spawn location from wiki research.

**Result:** Success after 6022ms, arrived at (3244, 3158).

### Phase 5: The Discovery Problem

**Command:** `query_nearby(account_id="aux", name_filter="net", include_ground_items=True)`

**Expected:** Find small fishing net on ground.

**Actual:**
```json
{
  "success": true,
  "ground_items": []
}
```

**Command:** `query_nearby(include_ground_items=True)` (no filter)

**Result:** Still empty `ground_items` array.

**Why this failed:** I assumed item spawns would be TileItems. They're not.

### Phase 6: Finding the Fishing Tutor (Landmark)

**Command:** `query_nearby(name_filter="tutor", include_npcs=True)`

**Why:** Confirm we're at the right location by finding nearby NPC.

**Result:**
```json
{
  "npcs": [{
    "name": "Fishing tutor",
    "distance": 1,
    "location": "WorldPoint(x=3245, y=3157, plane=0)"
  }]
}
```

**Lesson:** Fishing tutor confirmed location was correct. Problem was detection method, not position.

### Phase 7: The Solution - scan_tile_objects

**Command:** `scan_tile_objects(object_name="fishing net", max_distance=15)`

**Why:** After `query_nearby` failed, try scanning for GameObjects instead of TileItems.

**Result:**
```json
{
  "success": true,
  "count": 2,
  "objects": [
    {"name": "fishing net", "distance": 1, "x": 3244, "y": 3159, "type": "GameObject"},
    {"name": "fishing net", "distance": 2, "x": 3245, "y": 3156, "type": "GameObject"}
  ]
}
```

**Key insight:** The spawns are `type: "GameObject"` with ID 674, not ground items.

### Phase 8: Picking Up the Item

**Command:** `send_and_await(command="INTERACT_OBJECT fishing_net Take", await_condition="has_item:Small fishing net")`

**Why:**
- Used `INTERACT_OBJECT` because it's a GameObject, not `PICK_UP_ITEM` (which is for TileItems)
- Used underscores (`fishing_net`) per CLAUDE.md naming rules for multi-word objects
- Used `await_condition` to confirm item entered inventory

**Result:** Success after 6017ms. Inventory now contains "Small fishing net".

## Key Lessons

### 1. Static Item Spawns are GameObjects

**What happened:** `query_nearby(include_ground_items=True)` found nothing at a known item spawn.

**Why:** OSRS has two item-on-ground systems. Permanent spawns are GameObjects, not TileItems.

**Solution:**
```python
# BAD - only finds dropped/dynamic items
query_nearby(include_ground_items=True, name_filter="net")  # Returns []

# GOOD - finds static spawns (GameObject type)
scan_tile_objects(object_name="fishing net")  # Returns 2 objects
```

### 2. Use INTERACT_OBJECT for Item Spawns

**What happened:** Found items via `scan_tile_objects`, needed correct pickup command.

**Why:** GameObjects use `INTERACT_OBJECT`, TileItems use `PICK_UP_ITEM`.

**Solution:**
```python
# For static item spawns (GameObjects)
send_command("INTERACT_OBJECT fishing_net Take")

# For dropped items (TileItems)
send_command("PICK_UP_ITEM Bucket")
```

### 3. Plugin Freeze Detection via State File Staleness

**What happened:** Command failed with "Plugin appears frozen - state file is 81s stale".

**Why:** Plugin writes state every GameTick (~600ms). Staleness >30s = freeze.

**Solution:**
```python
# MCP tools auto-detect this, but manual check:
health = check_health()
if health["state_file"]["age_seconds"] > 30:
    start_runelite(account_id="aux")  # Restart
```

### 4. Screenshot Verification During Recovery

**What happened:** After restart, `await_state_change` returned immediately with stale data.

**Why:** State file from old session was still present with old timestamp.

**Solution:**
```python
# Don't trust state file immediately after restart
start_runelite(account_id="aux")
get_screenshot()  # Visual verification - saw "Connecting to server..."
await_state_change(condition="idle", timeout_ms=45000)
get_screenshot()  # Confirm actually logged in
```

## Anti-Patterns

1. **Don't** assume `query_nearby(include_ground_items=True)` finds all items on ground - it only finds TileItems, not GameObject spawns
2. **Don't** trust state file immediately after client restart - take a screenshot to verify actual state
3. **Don't** use `PICK_UP_ITEM` for static spawns - use `INTERACT_OBJECT <name> Take`

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `scan_tile_objects(object_name="X")` | Find static spawns (GameObjects) |
| `query_nearby(include_ground_items=True)` | Find dropped items (TileItems) |
| `get_screenshot()` | Visual verification when state file is unreliable |
| `query_nearby(name_filter="tutor", include_npcs=True)` | Landmark verification |

## Interface Gaps Identified

- [x] **Solved:** Use `scan_tile_objects` for static item spawns
- [ ] **MCP bug:** `restart_if_frozen` calls undefined `stop` method on manager
- [ ] **MCP gap:** Instance tracking lost after crash, `stop_runelite` reports "No instance"
- [ ] **Documentation:** CLAUDE.md should clarify GameObject spawns vs TileItems

## Decision Tree for Finding Items

```
Need to find an item on ground?
├── Is it a permanent spawn (respawns in same spot)?
│   └── YES → scan_tile_objects(object_name="X") → INTERACT_OBJECT X Take
│   └── NO → query_nearby(include_ground_items=True) → PICK_UP_ITEM X
```

## Time Analysis

| Phase | Time Spent | Notes |
|-------|-----------|-------|
| Wiki research | ~10s | WebFetch worked first try |
| Plugin freeze recovery | ~60s | 3 failed attempts before fresh start |
| Navigation | ~6s | GOTO worked once plugin was live |
| Discovery problem | ~30s | Wrong tool (`query_nearby`) |
| Solution | ~6s | `scan_tile_objects` + `INTERACT_OBJECT` |

**Total debugging time for item spawn issue:** ~30-60s once I realized `query_nearby` wasn't finding anything. The key insight was trying `scan_tile_objects` as an alternative.
