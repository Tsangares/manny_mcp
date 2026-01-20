# INTERACT_OBJECT Menu Index Mismatch - Lessons Learned
**Date:** 2026-01-18

## The Problem

`INTERACT_OBJECT Tin Mine` consistently clicks "Examine" instead of "Mine" even though "Mine" is visible in the menu. The system reports finding the option at the wrong array index.

## Root Cause

**NOT FULLY DIAGNOSED** - Investigation ongoing.

The bug manifests as an index mismatch between what the search finds and what actually gets clicked:

```
Menu after right-click:
  [0] Option='Cancel'
  [1] Option='Examine' | Target='Tin rocks'
  [2] Option='Walk here'
  [3] Option='Mine' | Target='Tin rocks'

Found option 'Mine' at targetIndex=1  <-- BUG: Mine is at [3], not [1]!

[MENU-VERIFY] Expected: 'Mine', Actual: 'Examine'  <-- Clicked wrong option
```

### Initial Hypothesis (Partial Fix Applied)

**Object name mismatch:**
- `findTileObjectsByName("Tin")` returns objects named "Tin"
- Menu shows target as "Tin rocks" (with color tags `<col=ffff>`)
- Target matching `"tin rocks".contains("tin")` should work but may have issues

**Fix attempted:** Changed `clickMenuEntrySafe(action, objectName, entries)` to `clickMenuEntrySafe(action, "", entries)` in InteractionSystem.java (lines 601, 674). This makes the search match action only, ignoring target name.

### Deeper Issue (Unresolved)

The log shows `Found option 'Mine' at targetIndex=1` but Mine is at index [3]. This suggests the search loop is returning the wrong index.

Tracing `matchesMenuEntry` logic for entry[1] (Examine):
```java
option = "Mine", target = "" (after fix)
entryOption = "examine"
optionMatch = "examine".contains("mine") = false  // Should NOT match!
targetMatch = "".isEmpty() = true
finalMatch = false && true = false  // Should return false!
```

**The search SHOULD NOT match Examine for "Mine".** Yet it reports targetIndex=1.

Possible causes:
1. Race condition between menu fetch and search
2. String encoding/invisible character issue
3. Different code path being executed
4. Log output doesn't reflect actual values being compared

## Key Lessons

### 1. Menu Array Order vs Visual Order

**What happens:** OSRS stores menu entries bottom-to-top in the array.
**Visual mapping:**
```
Array indices:          Rendered menu (top to bottom):
[3] Mine                Mine         <- TOP of menu
[2] Walk here           Walk here
[1] Examine             Examine
[0] Cancel              Cancel       <- BOTTOM of menu
```

The click position calculation DOES account for this (line 5659):
```java
int reversedIndex = entries.length - 1 - targetIndex;
```

But if `targetIndex` is wrong to begin with, the reversal makes it click on the wrong item.

### 2. Object Definition Names vs Menu Target Names

| Source | Name |
|--------|------|
| `findTileObjectsByName()` | "Tin" |
| Right-click menu target | "Tin rocks" |
| With color tags | `<col=ffff>Tin rocks` |

Object definition names (from ObjectComposition) don't always match what appears in the right-click menu.

### 3. Two Searches Happen

```
1. FIRST search (lines 5455-5481): Before right-click decision
   - Uses original hover menu entries
   - Determines if option is first (left-click) or not (right-click needed)

2. SECOND search (lines 5613-5622): After right-click
   - Re-fetches menu entries
   - Menu may have CHANGED (rock depleted, etc.)
   - Uses same option/target parameters
```

The second search resets `targetIndex = -1` and searches fresh. But somehow reports wrong index.

## Anti-Patterns

1. **Don't** assume menu entries are static - they change when right-click menu opens
2. **Don't** rely solely on object definition names for menu target matching
3. **Don't** trust log output without verifying with DEBUG-level `[MATCH]` logs

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(level="ALL", since_seconds=30)` | See DEBUG-level `[MATCH]` logs showing exact comparison values |
| `get_logs(grep="MENU-DEBUG")` | See menu entries and found index |
| `get_logs(grep="MENU-VERIFY")` | See expected vs actual click result |

## Interface Gaps Identified

- [ ] Need DEBUG-level matching logs visible at INFO level when mismatch occurs
- [ ] Need to log EACH entry's match result, not just final found index
- [ ] Consider adding entry-by-entry trace logging when `targetIndex == -1`

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/InteractionSystem.java:601` | Changed target param from `objectName` to `""` (partial fix) |
| `manny_src/utility/InteractionSystem.java:674` | Same change for TileObject path |

## Next Steps to Debug

1. Add INFO-level logging inside the search loop showing each entry checked
2. Log the actual string bytes to detect encoding issues
3. Verify the menu entries array isn't being modified between log and search
4. Check if there's a different `matchesMenuEntry` or search path being executed
