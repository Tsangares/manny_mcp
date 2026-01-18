# Indoor Navigation and Questing - Lessons Learned
**Date:** 2025-01-16

## The Problem

During The Restless Ghost quest, multiple navigation failures occurred:
1. Couldn't reach coffin in fenced graveyard - "I can't reach that!"
2. Couldn't find way down to Wizard Tower basement - staircase only goes UP
3. Object interactions silently failed due to case sensitivity
4. `USE_ITEM_ON_OBJECT` failed on open coffin (impostor object issue)

## Root Causes

### 1. No Visibility Into Path Blocking
When `GOTO` fails, there's no indication WHY. The player just stops. Without understanding that a fence/wall/door is blocking, I kept retrying the same failing command.

### 2. `query_nearby()` Excludes WallObjects
Doors, gates, and fences are WallObjects. `query_nearby()` only returns GameObjects, NPCs, and GroundItems - so doors were invisible to me.

**Working alternative:** `scan_tile_objects("door")` searches ALL TileObject types including WallObjects.

### 3. Case Sensitivity in INTERACT_OBJECT
Object names are **case-sensitive**:
```python
# FAILS silently
send_command("INTERACT_OBJECT coffin Open")

# WORKS
send_command("INTERACT_OBJECT Coffin Open")
```

The scan returns lowercase `coffin` but the game expects `Coffin`. Always scan first and use the exact name.

### 4. Wizard Tower Has Two Staircase Types
- Staircase at (3103, 3159) - only has `Climb-up` action
- Ladder at (3104, 3162) - has `Climb-down` action to basement

I assumed "staircase" meant bidirectional. It doesn't. Use `get_transitions()` to see available actions.

## Key Lessons

### 1. Always Use get_transitions() Before Indoor Navigation

**What happened:** Walked to graveyard coffin, couldn't interact, didn't know why.
**Why:** Door at (3247, 3193) was blocking access - invisible without scanning.
**Solution:**
```python
# BEFORE any indoor action
transitions = get_transitions(radius=15)
# Returns: {"nearest": [{"type": "door", "name": "Door", "state": "closed", "direction": "south"}]}

# Now I know to open the door first!
send_command("INTERACT_OBJECT Door Open")
```

### 2. Scan For Exact Object Names Before Interacting

**What happened:** `INTERACT_OBJECT coffin Open` silently failed.
**Why:** Case mismatch - game uses `Coffin`.
**Solution:**
```python
# BAD - guessing the name
send_command("INTERACT_OBJECT coffin Open")

# GOOD - scan first, use exact name
scan_tile_objects("coffin")
# Returns: {"name": "coffin", ...} -- wait, lowercase?
# Try capitalized anyway since OSRS displays names that way
send_command("INTERACT_OBJECT Coffin Open")  # Works!
```

### 3. Verify Transition Actions, Don't Assume

**What happened:** Went to staircase expecting `Climb-down`, only had `Climb-up`.
**Why:** Wizard Tower has separate objects for up/down.
**Solution:**
```python
# Use get_transitions() to see actual actions
transitions = get_transitions()
# Shows: {"stairs": [{"actions": ["Climb-up"], ...}],
#         "ladders": [{"actions": ["Climb-down"], ...}]}
# Now I know: use LADDER to go down, not staircase!
```

### 4. New Tool: get_transitions() (Implemented This Session)

The `get_transitions()` MCP tool was implemented during this session to solve indoor navigation issues:

```python
get_transitions(radius=15)
# Returns:
# {
#   "nearest": [
#     {"type": "door", "name": "Door", "distance": 3, "direction": "south", "state": "closed"}
#   ],
#   "transitions": {
#     "doors": [...],
#     "stairs": [...],
#     "ladders": [...],
#     "portals": [...]
#   },
#   "summary": "Nearest: Door (closed) 3 tiles south, Ladder 20 tiles northwest"
# }
```

The `nearest` array shows one of each type sorted by distance - perfect for quick decision making.

## Anti-Patterns

1. **Don't use GOTO directly to indoor destinations** - Always check get_transitions() first
2. **Don't guess object names** - Scan first to get exact capitalization
3. **Don't assume stairs are bidirectional** - Check available actions
4. **Don't ignore "I can't reach that!" errors** - Means path is blocked, scan for doors

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_transitions(radius=20)` | See all doors, stairs, ladders with state and distance |
| `scan_tile_objects("door", max_distance=25)` | Find doors (larger radius for distant ones) |
| `get_logs(level="ALL", grep="INTERACT")` | Check if command executed and why it failed |
| `get_command_response()` | See actual success/failure after command |

## Interface Gaps Identified

- [x] Added `get_transitions()` MCP tool with nearest array
- [x] Added `QUERY_TRANSITIONS` plugin command
- [ ] `query_nearby()` still doesn't include WallObjects (document workaround: use scan_tile_objects)
- [ ] Object name case sensitivity should be documented more prominently
- [ ] Navigation could report WHY it failed (blocked by wall at X,Y)

## Files Modified

| File | Change |
|------|--------|
| `mcp_server.py` | Added get_transitions() MCP tool |
| `PlayerHelpers.java` | Added QUERY_TRANSITIONS command |
| `PlayerHelpers.java:14454-14527` | Fixed impostor handling in USE_ITEM_ON_OBJECT |
| `routines/quests/restless_ghost.yaml` | Updated with all lessons learned |

## Navigation Protocol (For Future Quests)

```python
# 1. SCAN environment before any indoor action
transitions = get_transitions(radius=15)

# 2. CHECK for blocking doors
if any(t["state"] == "closed" for t in transitions["transitions"]["doors"]):
    # Open nearest closed door
    send_command("INTERACT_OBJECT Door Open")

# 3. VERIFY door opened
transitions = get_transitions()
assert transitions["nearest"][0]["state"] == "open"

# 4. NOW proceed to destination
send_command("GOTO x y plane")

# 5. SCAN object before interacting
scan_tile_objects("target_object")
# Use exact name from scan result
send_command("INTERACT_OBJECT ExactName Action")
```

## Quest Completion Summary

**The Restless Ghost** completed after fixing:
- Graveyard door blocking (opened with INTERACT_OBJECT Door Open)
- Case sensitivity (Coffin not coffin)
- Wizard Tower navigation (Ladder not Staircase for basement)
- USE_ITEM_ON_OBJECT impostor handling (plugin fix)

**Rewards:** 1 Quest Point, 1125 Prayer XP, Ghostspeak amulet (kept)
