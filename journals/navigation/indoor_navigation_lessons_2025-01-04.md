# Indoor Navigation Lessons Learned
**Date:** 2025-01-04
**Context:** Attempting to navigate Lumbridge Castle to reach the Cooking Range

## The Disaster

Claude attempted to navigate from the castle main floor to the kitchen range. What should have been a simple walk turned into:
1. Clicking toward the range **through a wall** (naive GOTO failed)
2. Opening the **nearest door** which led into a side room (trapped!)
3. Confusion between "Door", "Large door", "Large_door", and "Trapdoor"
4. Multiple failed attempts before finally reaching the range

## Root Causes

### 1. No Pre-Navigation Scanning
**What happened:** Immediately tried `GOTO 3212 3215 0` without checking surroundings.
**Should have done:** `scan_tile_objects("Door")` first to understand the room layout.

### 2. "Nearest Door" Trap
**What happened:** `INTERACT_OBJECT Door Open` opened the nearest door, which was a side room door, not the exit.
**Lesson:** There are often multiple doors nearby. Must identify WHICH door leads to the destination.

### 3. Object Name Confusion
| Tried | Actual Name | Issue |
|-------|-------------|-------|
| `Door Open` | `Large_door` | Wrong object entirely |
| `Large door` | `Large_door` | Missing underscore |
| `Range` | `Cooking range` | Incomplete name |
| `Raw shrimps` (for USE_ITEM) | Works with spaces | Items use spaces, objects use underscores |

**Rule:** Always `scan_tile_objects("partial_name")` to get the EXACT object name before interacting.

### 4. No Spatial Reasoning
**What happened:** No understanding of "I'm in room A, range is in room B, I need to go through door X."
**Should have done:** Build a mental model first:
- Current position
- Target position
- What's between them (walls, doors)
- Which doors connect which rooms

## The Protocol (What To Do Instead)

### Indoor Navigation Protocol

**BEFORE any indoor navigation:**

```
1. SCAN: scan_environment() or scan_tile_objects()
   - Get all nearby doors with exact names
   - Get all nearby objects of interest
   - Note player position

2. UNDERSTAND: Build mental model
   - "I am at (X, Y)"
   - "Target is at (A, B)"
   - "Doors visible: Large_door (north), Door (west), Trapdoor (down)"
   - "Target direction: south"
   - "Wall blocks direct path: yes/no"

3. PLAN: Route through doors
   - "To reach kitchen (south), I need to:"
   - "Exit through Large_door (north) to main hall"
   - "Walk south through main hall"
   - "Enter kitchen (no door needed, open archway)"

4. EXECUTE: Step by step with verification
   a. Walk to door: GOTO <door_tile>
   b. Open door: INTERACT_OBJECT Large_door Open
   c. Verify: Check response, get_game_state()
   d. Walk through: GOTO <next_waypoint>
   e. Repeat until destination reached

5. VERIFY: After each step
   - Position changed as expected?
   - If stuck, RE-SCAN and RE-PLAN
```

## Object Naming Rules

### Objects (scan_tile_objects, INTERACT_OBJECT)
- **Multi-word names use underscores:** `Large_door`, `Cooking_range`, `Bank_booth`
- **Always scan first** to get exact name
- **Case matters sometimes** - use exact case from scan

### Items (inventory, USE_ITEM_ON_OBJECT)
- **Use spaces:** `Raw shrimps`, `Pot of flour`
- **Check game state** for exact inventory item names
- **Plurals matter:** "Raw shrimps" not "Raw shrimp"

### Examples
```
# GOOD
INTERACT_OBJECT Large_door Open
INTERACT_OBJECT Cooking_range Cook
USE_ITEM_ON_OBJECT Raw shrimps Cooking_range

# BAD
INTERACT_OBJECT Large door Open  # Missing underscore
INTERACT_OBJECT Door Open        # Too generic, might get wrong door
INTERACT_OBJECT Range Cook       # Incomplete name
```

## Lumbridge Castle Mental Map

```
                    [Main Hall]
                    (3212, 3225)
                         |
                    Large_door
                         |
    [Side Room] --Door-- [Kitchen Area]
    (3218, 3218)        (3211, 3216)
                              |
                       Cooking_range
                        (3212, 3215)
                              |
                    [Outside courtyard]

Cellar (plane -1):
    Trapdoor (from kitchen) -> Mill basement
    Hopper, Flour bin for flour making
```

## Key Coordinates

| Location | Coordinates | Notes |
|----------|-------------|-------|
| Kitchen/Range | 3212, 3215, 0 | Cooking range here |
| Kitchen center | 3211, 3216, 0 | Safe standing spot |
| Main hall | 3212, 3225, 0 | Central area |
| Large door (N) | 3213, 3222, 0 | Kitchen to main hall |
| Side room door | 3218, 3217, 0 | DON'T use this one |

## Anti-Patterns to Avoid

1. **DON'T** click toward destination without scanning first
2. **DON'T** use `INTERACT_OBJECT Door Open` without specifying which door
3. **DON'T** assume object names - always scan for exact names
4. **DON'T** continue after failure without re-scanning
5. **DON'T** trust that "nearest" is "correct"

## Commands to Remember

| Command | Purpose | Example |
|---------|---------|---------|
| `scan_tile_objects` | Find exact object names | `scan_tile_objects("door")` |
| `query_nearby` | Get NPCs, objects, items | `query_nearby()` |
| `get_game_state` | Current position, inventory | Check after each move |
| `scan_environment` | Full spatial context | **NEW** - use before indoor nav |

## Future Improvements Implemented

1. **scan_environment()** - New MCP tool combining scans with spatial analysis
2. **Location knowledge base** - Pre-defined room data for common areas
3. **Navigation protocol** - Documented in CLAUDE.md for consistent behavior
