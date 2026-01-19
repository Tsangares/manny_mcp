# find_widget Returns Wrong Bounds for Inventory Items

**Created:** 2025-01-18
**Status:** FIXED
**Priority:** High (blocks basic inventory interaction)

## Problem

`find_widget()` correctly identifies inventory items by name and itemId, but returned **identical bounds** for all items - always pointing to the container position instead of the actual item's grid position.

## Root Cause

**ScanWidgetsCommand.java** used `widget.getBounds()` directly for inventory items (group 149 dynamic children), which returns the container's bounds instead of calculating each item's grid position based on slot index.

## Fix Applied

Added grid position calculation in `ScanWidgetsCommand.java` (lines 497-522):

```java
if (group == 149 && childIdx == 0 && slotIndex >= 0 && slotIndex < 28) {
    Widget container = client.getWidget(149, 0);
    java.awt.Rectangle containerBounds = container.getBounds();

    int cols = 4;
    int col = slotIndex % cols;
    int row = slotIndex / cols;
    int x = containerBounds.x + 13 + (col * 42);
    int y = containerBounds.y + 5 + (row * 36);

    bounds = new java.awt.Rectangle(x, y, 36, 32);
}
```

## Additional Fix Required

Even with correct bounds, `find_and_click_widget` was using `CLICK_WIDGET {id} "{action}"` which re-searches children and finds the wrong item. Changed to use `xdotool` for clicking at the calculated coordinates directly.

## Journal

See `journals/inventory_item_clicking_wrong_item_2026-01-18.md` for full analysis.
