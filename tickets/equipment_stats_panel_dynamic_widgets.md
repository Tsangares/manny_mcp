# Equipment Stats Panel - Dynamic Widget Issue

**Created:** 2025-01-18
**Status:** FIXED (with workaround)
**Priority:** Medium

## Problem

When the Equipment Stats panel is open (via "View equipment stats" button), inventory items returned bounds of **-1, -1** because the regular inventory (group 149) is hidden behind the panel.

## Root Cause

Tutorial Island's Equipment Stats panel displays a **fake inventory** as part of its interface, not the real group 149 inventory widget. The real inventory widget has invalid bounds when hidden.

## Fix Applied

1. **ScanWidgetsCommand.java** - Added grid position calculation that only applies when container bounds are valid (x >= 0)

2. **Workaround** - Close the Equipment Stats panel first (ESC key), then interact with the real inventory:

```python
send_command("KEY_PRESS Escape")  # Close panel
await asyncio.sleep(0.3)
find_and_click_widget(text="Bronze dagger")  # Now works
```

## Additional Context

This issue primarily affects Tutorial Island. The main game's equipment panel doesn't have this problem because the inventory tab remains accessible.

## Journal

See `journals/inventory_item_clicking_wrong_item_2026-01-18.md` for related fixes to inventory clicking.
