# Deposit Box Grid Positioning Fix

**Date:** 2025-01-08

## Problem

Deposit box item clicking was unreliable - the mouse would click on the wrong cell or miss items entirely when trying to deposit.

## Root Cause

The deposit box grid position calculation had incorrect offsets. The original code used arbitrary guesses (`x + 170`, `y + 15`) that were never visually verified.

### Why the offsets exist

The container widget (192, 2) `getBounds()` returns the **full deposit box window** including:
- Title bar ("Bank of Gielinor - Deposit Box")
- Decorative border/frame
- Internal padding/margins

The offset values account for this UI chrome to find where the actual item grid starts.

### Original (wrong) values
```java
int gridBaseX = containerBounds.x + 170;
int gridBaseY = containerBounds.y + 15;
```

### Corrected values
```java
int gridBaseX = containerBounds.x + 182;  // +12 from original
int gridBaseY = containerBounds.y + 7;    // -8 from original
```

## How we found the fix

1. **Built a debug overlay** (`DepositBoxGridOverlay`) that visualizes:
   - Yellow border around container widget bounds
   - Cyan origin marker at grid start
   - Green boxes for slots with items
   - Red crosshairs at click targets
   - Slot numbers and item IDs

2. **Observed misalignment** - the overlay grid was offset from actual item sprites

3. **Measured the error** - user reported ~23px right, ~16px up needed

4. **Applied half the measurement** - due to `-Dsun.java2d.uiScale=2.0`, screen pixels are 2x logical pixels

5. **Verified visually** - overlay now aligns perfectly with item sprites

## UI Scale consideration

The JVM runs with `-Dsun.java2d.uiScale=2.0`. This means:
- Widget bounds are in **logical pixels** (pre-scaled)
- Visual measurements on screen are in **physical pixels** (2x)
- A 24px screen measurement = 12 logical pixels in code

## Other fixes applied

### Two-phase mouse movement
```java
// Phase 1: Humanized movement
mouse.move(itemBounds[0]);

// Phase 2: Precise correction if missed
if (!itemBounds[0].contains(Mouse.mouseX, Mouse.mouseY)) {
    mouse.movePrecisely(itemBounds[0]);
}
```

### Grid layout constants
```
- Container offset: (182, 7) from widget bounds
- Cell size: 42x36 pixels (spacing between items)
- Item size: 36x32 pixels (actual clickable area)
- Grid: 4 columns x 7 rows (28 slots)
```

## Files modified

1. `manny_src/utility/commands/BankDepositItemCommand.java` - grid offset fix, two-phase mouse
2. `manny_src/utility/commands/ScanWidgetsCommand.java` - grid offset fix for widget scanning
3. `manny_src/ui/UIOverlays.java` - added `DepositBoxGridOverlay` (Section 10)
4. `manny_src/MannyPlugin.java` - registered new overlay

## Lesson learned

**Always build visual debug tools** for coordinate calculations. Guessing pixel offsets without verification leads to subtle bugs that are hard to diagnose. The overlay took 10 minutes to build and immediately revealed the problem.

## MCP tool added

Added `deposit_item` MCP tool in `mcptools/tools/commands.py` for easy deposit operations:
```python
deposit_item(item_name="Raw lobster", wait_for_completion=True)
```
