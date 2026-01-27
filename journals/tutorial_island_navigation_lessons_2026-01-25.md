# Tutorial Island Navigation - Lessons Learned
**Date:** 2026-01-25

## The Problem

Navigation from the cooking section to Quest Guide building kept failing. GOTO commands timed out, player got stuck in loops returning to starting area, and the "correct" door couldn't be found despite being visible on screen.

## Root Cause

1. **Invisible fences** block direct north paths on Tutorial Island. The game world has collision geometry not visible in screenshots.
2. **Door interaction requires proximity** - INTERACT_OBJECT fails silently if not standing directly in front of door.
3. **Two doors exist in cooking building** - one leads backward (toward Gielinor Guide), one leads forward (toward Quest Guide). Easy to pick wrong one.

## Key Lessons

### 1. Walk IN FRONT of Doors Before Interacting

**What happened:** `INTERACT_OBJECT door Open` succeeded but player didn't move through, or command failed entirely.
**Why:** The plugin finds the nearest matching object, but interaction requires being at the correct tile adjacent to the door.
**Solution:**
```python
# BAD - Interact from wherever you are
send_command("INTERACT_OBJECT door Open")  # May fail silently

# GOOD - Walk to door tile first, then interact
send_and_await("GOTO 3073 3090 0", "location:3073,3090")  # In front of door
send_command("INTERACT_OBJECT door Open")  # Now works reliably
```

### 2. Navigate WEST First to Avoid Invisible Fences

**What happened:** Direct GOTO north from cooking area (Y: 3090 → 3120) repeatedly failed with "Navigation failed".
**Why:** Tutorial Island has invisible fence collision between the cooking area and Quest Guide area. The fence runs roughly north-south around X: 3080-3089.
**Solution:**
```python
# BAD - Direct path blocked by invisible fence
send_command("GOTO 3086 3126 0")  # Fails - fence in the way

# GOOD - Go west first, then north along western edge
send_command("GOTO 3072 3100 0")  # West side - no fence
send_command("GOTO 3072 3110 0")  # Continue north
send_command("GOTO 3080 3120 0")  # Now safe to go east
send_command("GOTO 3086 3125 0")  # Arrive at Quest Guide door
```

### 3. Use Incremental Waypoints, Not Single Long GOTOs

**What happened:** Single GOTO commands covering 20+ tiles often timed out even when path was technically clear.
**Why:** Pathfinding may find suboptimal routes, get stuck on minor obstacles, or simply take too long. Tutorial Island terrain is particularly tricky.
**Solution:**
```python
# BAD - One big jump
send_and_await("GOTO 3086 3126 0", "location:3086,3126", timeout_ms=30000)

# GOOD - Multiple smaller steps
send_and_await("GOTO 3072 3100 0", "location:3072,3100", timeout_ms=10000)
send_and_await("GOTO 3080 3120 0", "location:3080,3120", timeout_ms=10000)
send_and_await("GOTO 3086 3125 0", "location:3086,3125", timeout_ms=10000)
```

### 4. Get User Help for Tricky Manual Navigation

**What happened:** Spent many tool calls trying different paths, all failing.
**Why:** Some navigation problems are faster to solve with human intervention than algorithmic trial-and-error.
**Solution:** When stuck on navigation for 5+ attempts, ask user: "Can you walk me to [location]?" Then document the working path in YAML.

## Anti-Patterns

1. **Don't** assume GOTO will find any valid path - Tutorial Island has invisible collision
2. **Don't** use the "nearest door" without verifying it leads the right direction
3. **Don't** try coordinate-based clicking (`send_input click x y`) - causes server disconnections on Tutorial Island
4. **Don't** skip the "walk in front of door" step - door interactions are position-sensitive

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_transitions(radius=20)` | Find all doors/gates/ladders with open/closed state |
| `scan_tile_objects("door", max_distance=25)` | Find door coordinates to plan approach |
| `scan_widgets(group=263)` | Read current tutorial hint to verify progress |
| Screenshot via `import -window` | See actual game state when tools disagree |

## Interface Gaps Identified

- [x] MCP `get_transitions` works well for finding doors
- [ ] Plugin needs: Pathfinding debug mode to show WHY navigation failed (obstacle location)
- [ ] CLAUDE.md needs: Document Tutorial Island invisible fence locations
- [ ] Routine YAML needs: Mandatory `approach_position` field before door interactions

## Validated Path: Cooking → Quest Guide

```yaml
# Working waypoints (MUST follow this order)
- {x: 3073, y: 3090}  # In front of cooking exit door
- {x: 3072, y: 3100}  # North along WEST edge (avoids fence)
- {x: 3072, y: 3110}  # Continue north
- {x: 3080, y: 3120}  # Turn east toward Quest Guide
- {x: 3086, y: 3125}  # Quest Guide door
```

## Files Modified

| File | Change |
|------|--------|
| `routines/tutorial_island/05_cooking_to_quest_guide.yaml` | Created with validated path |
| `routines/tutorial_island/widget_reference.yaml` | Added navigation discoveries section |

## Time Cost

~30 minutes of failed GOTO attempts before user intervention revealed the correct path. Key insight: invisible fences require west-first routing.
