# Location History Enhancements for YAML Routine Review

**Created:** 2026-01-26
**Priority:** Medium
**Status:** Open

## Overview

Improve the location history feature (`/tmp/manny_<account>_location_history.json`) to be more useful for reviewing and generating YAML routines automatically.

## Current State

The location history currently tracks:
- Movement coordinates (x, y, plane) with timestamps
- Dialogue options clicked
- Session duration and event count

**Example current output:**
```json
{"ts":1769486737610,"x":3130,"y":3104,"plane":0,"eventType":"move"}
{"ts":1769486814994,"x":3126,"y":3105,"plane":0,"eventType":"dialogue","command":"CLICK_DIALOGUE \"Brother Brace\"","dialogueOption":"Brother Brace"}
```

## Problem

The current data is too granular for movement (every tile) and missing key information needed to generate YAML routines:
- No object interactions (doors, ladders, banks)
- No NPC interactions (only dialogue choices, not who was talked to)
- No inventory changes
- No plane change triggers
- Movement not consolidated into meaningful waypoints

## Proposed Enhancements

### 1. Add command context
Track the MCP command that triggered each action:
```json
{"ts":..., "eventType":"door", "command":"INTERACT_OBJECT Door Open", "object":"Door", "x":3122, "y":3102}
```

### 2. Add object/NPC interactions
```json
{"ts":..., "eventType":"npc_interact", "npc":"Magic_Instructor", "action":"Talk-to", "x":3141, "y":3088}
{"ts":..., "eventType":"object_interact", "object":"Bank_booth", "action":"Use", "x":3120, "y":3123}
```

### 3. Add inventory deltas
Track items gained/lost at each significant event:
```json
{"ts":..., "eventType":"inventory", "gained":["Air rune x5", "Mind rune x5"], "lost":[]}
```

### 4. Consolidate movement into waypoints
Instead of every tile, show walk segments:
```json
{"ts":..., "eventType":"walk", "from":{"x":3130,"y":3104}, "to":{"x":3141,"y":3089}, "tiles":15, "duration_ms":8000}
```

### 5. Add plane changes explicitly
```json
{"ts":..., "eventType":"plane_change", "from":0, "to":1, "trigger":"Ladder Climb-up", "x":3123, "y":3128}
```

### 6. Add location labels for known areas
```json
{"ts":..., "x":3141, "y":3089, "area":"tutorial_island_magic"}
```

## Relevant Files

- `/home/wil/manny-mcp/mcptools/tools/location_history.py` - Python MCP tool
- `/home/wil/manny-mcp/mcptools/tools/routine_generator.py` - Routine generation from history
- `/home/wil/manny-mcp/server.py` - Server integration
- `/home/wil/manny-mcp/mcptools/config.py` - Config
- `journals/event_recording_routine_generation_2026-01-26.md` - Related journal entry
- Java plugin code that writes events to the JSON file

## Testing: Code Generation from History

After implementing enhancements, test automatic YAML generation:

1. Record a manual play session with enhanced tracking
2. Run `session_to_routine` on the recorded history
3. Compare generated YAML to hand-written routines (e.g., Tutorial Island YAMLs)
4. Execute generated routine to verify it works

**Test case:** Record completing Tutorial Island magic section manually, generate YAML, compare to `routines/tutorial_island/10_prayer_magic.yaml`

## Acceptance Criteria

- [ ] Object interactions tracked (doors, ladders, booths, etc.)
- [ ] NPC interactions tracked with name and action
- [ ] Inventory changes tracked (items gained/lost)
- [ ] Movement consolidated into waypoints (not every tile)
- [ ] Plane changes explicitly logged with trigger
- [ ] Location labels for known areas
- [ ] Can generate valid YAML from recorded session
- [ ] Generated YAML executes successfully

## Notes

This feature would significantly speed up routine creation by allowing:
1. Play through content manually once
2. Auto-generate YAML from the recording
3. Minor cleanup/validation of generated YAML
4. Ready-to-use routine
