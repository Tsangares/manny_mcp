# TODO

## Pending Investigation (Runtime Issues)

These commands exist but may have runtime bugs to investigate:

### INTERACT_OBJECT - Windmill Door Issue
**Status:** Needs Testing
**Source:** MCP_IMPROVEMENT_PROPOSAL.md, quest_cooks_assistant.md

The command exists but reportedly fails to find the windmill door. May be:
- Object name mismatch (try "Door" vs "Large door")
- Distance/visibility issue
- Need to use `query_nearby` to discover correct object name

**To Test:**
```
send_command("FIND_OBJECT Door")
send_command("FIND_OBJECT Large door")
query_nearby(name_filter="door")
```

### Shop Interaction
**Status:** Needs Testing
**Source:** quest_cooks_assistant.md

SHOP_BUY command exists but shop opening via INTERACT_NPC may be unreliable.

**To Test:**
```
send_command("INTERACT_NPC Shopkeeper Trade")
send_command("SHOP_BUY Bucket 1")
```

### Navigation Stuck Detection
**Status:** Monitor during testing
**Source:** quest_cooks_assistant.md

Navigation can get stuck on long routes or near obstacles. Watch for:
- Gates/fences blocking path
- Stuck at same position for 60+ seconds
- Routes > 80 tiles

### Pathfinding Door/Fence Auto-Detection
**Status:** Partially Fixed (2026-01-03)
**Source:** Testing session 2026-01-03

**Fixed:**
- Pathfinder API path now detects stuck situations when player can't reach waypoint
- Stuck detection scans for nearby gates/doors/fences/stiles
- Automatically attempts to open/climb blocking obstacles and resumes navigation
- Fixed `attemptOpenGate()` double right-click bug (was causing stale menu entries)
- Added support for multiple obstacle actions: "Open", "Climb-over", "Push", "Enter", "Pass"
- Added "stile" to obstacle name detection

**Still to test:**
- Verify obstacle handling works reliably in practice
- Test with various obstacle types (gates, doors, stiles, fences)

**Code changes:**
- `gotoPositionSafe()` lines 2913-2948: Added gate detection on waypoint timeout
- `attemptOpenGate()` lines 3668-3675: Fixed redundant right-click

---

## Future Ideas (Deferred)

### Routine Entry Point Validation
**Status:** Deferred - not implementing now
**Date:** 2026-01-08
**Discussion:** Plan exists at `.claude/plans/jaunty-strolling-dream.md`

Add `preconditions` section to routine YAML that validates before step 1:
- Location check (within ~15 tiles of start location)
- Required items check (inventory has lobster pot, coins, etc.)
- Plane check (on correct floor)

**Why deferred:** Still working on more fundamental issues (doors, menus, clicking). Entry point validation is polish for later when routines are more stable.

**Quick summary:**
- Fail fast with helpful error ("Missing: Lobster pot" or "Not at Port Sarim")
- Start with fishing_karamja_lobster.yaml as test case
- ~50 lines of Python in `routine.py`

---

## Completed

### Plugin Commands (All Implemented)
| Command | Status | Notes |
|---------|--------|-------|
| `CLIMB_LADDER_UP` | ✅ Done | Line 9388 |
| `CLIMB_LADDER_DOWN` | ✅ Done | Line 9391 |
| `PICK_UP_ITEM` | ✅ Done | Line 9197 |
| `SHOP_BUY` | ✅ Done | Line 9375 |
| `INTERACT_NPC` | ✅ Done | Line 9382 |
| `INTERACT_OBJECT` | ✅ Done | Line 9385 |
| `FIND_OBJECT` | ✅ Done | Line 9316 |

### Query Commands (Implemented 2026-01-03)
| Command | Status | Notes |
|---------|--------|-------|
| `QUERY_EQUIPMENT` | ✅ New | Returns equipped items as JSON |
| `SCAN_BANK` | ✅ New | Lists all bank contents |
| `QUERY_PLAYERS` | ✅ New | Scans nearby players |
| `DESELECT` | ✅ New | Clears item/spell selection (presses Escape) |

### Bug Fixes (2026-01-03)
| Issue | Status | Notes |
|-------|--------|-------|
| DROP_ALL menu stuck | ✅ Fixed | Added `clearOpenMenus()` at start/end of drop operation |
| Gate opening double-click | ✅ Fixed | Removed redundant right-click in `attemptOpenGate()` |

### MCP Tools (All Implemented)
| Tool | Status |
|------|--------|
| `list_available_commands` | ✅ Done |
| `get_command_examples` | ✅ Done |
| `validate_routine_deep` | ✅ Done |
| `query_nearby` | ✅ Done |
| `find_command` | ✅ Done |

