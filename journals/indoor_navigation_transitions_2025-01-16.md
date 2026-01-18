# Indoor Navigation - WallObjects and Transition Detection
**Date:** 2025-01-16

## The Problem

Indoor navigation repeatedly failed with "I can't reach that!" errors. Doors blocking paths were invisible to standard scanning tools, leading to wasted attempts and misdiagnosed "case sensitivity" issues.

## Root Cause

`query_nearby()` only returns GameObjects - it **excludes WallObjects** (doors, gates, fences). When navigating indoors, the critical blockers (closed doors) were invisible.

The suspected "case sensitivity" issue (e.g., "coffin" vs "Coffin") was a misdiagnosis. Investigation revealed:
- `findGameObjectsByName()` - already uses `.toLowerCase().contains()` (GameEngine.java:1904)
- `findTileObjectsByName()` - already uses `.toLowerCase().contains()` (GameEngine.java:1996)
- `getNPC()` - already uses `.toLowerCase()` (GameEngine.java:1178)
- `matchesMenuEntry()` - already uses `.toLowerCase()` (PlayerHelpers.java:5371)

The real issue was **not seeing doors at all**, not case-sensitive matching.

## Key Lessons

### 1. WallObjects Are Invisible to query_nearby

**What happened:** Attempted to reach a coffin behind a fence. `query_nearby()` showed the coffin but no fence or door.

**Why:** `query_nearby()` only queries GameObjects. Doors, gates, and fences are WallObjects - a different TileObject type.

**Solution:** Use `get_transitions()` or `scan_tile_objects()` which search ALL TileObject types:
```python
# BAD - misses doors/gates/fences
query_nearby()  # Only GameObjects

# GOOD - finds all navigable transitions including WallObjects
get_transitions(radius=15)
# Returns: doors, stairs, ladders, trapdoors, portals, gates
# Includes open/closed state!
```

### 2. Door State Detection via Actions

**What happened:** Couldn't tell if a door was open or closed without trying to interact.

**Why:** Doors have either "Open" or "Close" action based on current state.

**Solution:** `get_transitions()` automatically detects state:
```python
# State detection logic (in plugin):
# "Open" action present → door is CLOSED
# "Close" action present → door is OPEN

transitions = get_transitions()
# Response includes: {"state": "closed", "actions": ["Open"]}
```

### 3. Don't Misdiagnose Without Checking

**What happened:** Assumed case sensitivity when "coffin" didn't work. Spent time planning a fix for a non-issue.

**Why:** The actual problem (door blocking path) was invisible. Brain jumped to "name must be wrong" without evidence.

**Solution:** Always check logs first:
```python
# When INTERACT_OBJECT fails, check logs IMMEDIATELY
get_logs(level="ALL", grep="INTERACT")
# Shows: "TileObject 'coffin' not found" vs "Path blocked"

# Then scan for blockers
get_transitions()  # See doors/gates in the way
```

## Anti-Patterns

1. **Don't assume query_nearby shows everything** - It misses WallObjects (doors, fences)
2. **Don't diagnose without logs** - "Case sensitivity" was wrong; logs would have shown the real error
3. **Don't use multiple scan_tile_objects calls** - Use `get_transitions()` which scans all transition types in one call

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_transitions()` | Find ALL navigable transitions (doors, stairs, ladders) with state |
| `scan_tile_objects("door")` | Search for specific object type including WallObjects |
| `get_logs(grep="INTERACT")` | See what actually happened when interaction failed |

## Interface Gaps Identified

- [x] Plugin needs: `QUERY_TRANSITIONS` command - **DONE** (existed already)
- [x] MCP needs: `get_transitions()` wrapper - **DONE** (added in spatial.py)
- [x] CLAUDE.md needs: Documentation about WallObjects - **DONE** (Indoor Navigation Protocol updated)

## Files Modified

| File | Change |
|------|--------|
| `mcptools/tools/spatial.py` | Added `get_transitions()` MCP tool wrapping QUERY_TRANSITIONS |
| `manny_src/actions/Actions.java:3795` | Changed `equals()` to `equalsIgnoreCase()` for consistency |
| `CLAUDE.md` | Updated Indoor Navigation Protocol to recommend `get_transitions()` |

## Key Takeaway

The **observability gap** was the real problem. When you can't see doors, you blame the wrong thing (case sensitivity). The fix wasn't better matching - it was better scanning via `get_transitions()`.
