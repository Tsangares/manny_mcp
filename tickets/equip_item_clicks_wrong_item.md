# equip_item() Clicks Wrong Inventory Item

**Created:** 2025-01-18
**Status:** FIXED (pending MCP restart)
**Priority:** High

## Problem

`equip_item(item_name="X")` sends `CLICK_WIDGET 9764864 "Wield"` which clicks the **first** item with a "Wield" action, not the specific item requested.

## Example

```python
# Inventory has: Bronze dagger, Bronze axe, Bronze pickaxe, Bronze sword, Wooden shield
equip_item(item_name="Bronze sword")
# Expected: Equips Bronze sword
# Actual: Equips Bronze dagger (first "Wield"-able item)
```

## Root Cause

`equip_item()` in the MCP tools uses `CLICK_WIDGET <container_id> "<action>"` which:
1. Finds widget 9764864 (inventory container)
2. Searches for first child with "Wield" action
3. Clicks that child - **ignoring the item_name parameter**

The item_name is only used to find the widget and determine the action (Wield/Wear), but the actual click command doesn't use it.

## Workaround

Use `find_widget` + `MOUSE_MOVE` + `MOUSE_CLICK`:

```python
# 1. Find specific item bounds
result = find_widget(text="Wooden shield")
bounds = result["widgets"][0]["bounds"]

# 2. Move to center of bounds
center_x = bounds["x"] + bounds["width"] // 2
center_y = bounds["y"] + bounds["height"] // 2
send_command(f"MOUSE_MOVE {center_x} {center_y}")

# 3. Click
send_command("MOUSE_CLICK left")
```

## Suggested Fix

Option A: Fix `equip_item()` to use the workaround internally
- After finding the item with find_widget, use MOUSE_MOVE + MOUSE_CLICK at the bounds

Option B: Fix `CLICK_WIDGET` command to accept item name
- `CLICK_WIDGET 9764864 "Wield" "Bronze sword"` - click widget with action "Wield" AND item name "Bronze sword"

Option C: Add new command `EQUIP_ITEM <item_name>`
- Plugin handles finding and clicking the correct inventory slot

## Fix Applied

Changed `equip_item()` in `mcptools/tools/commands.py` to use xdotool with the found widget's bounds instead of `CLICK_WIDGET`:

```python
# OLD (broken) - re-searches and finds first match
click_command = f'CLICK_WIDGET {widget_id} "{equip_action}"'

# NEW (fixed) - clicks at the bounds we already found
bounds = inventory_widget.get("bounds", {})
click_x = bounds["x"] + bounds["width"] // 2
click_y = bounds["y"] + bounds["height"] // 2
subprocess.run(["xdotool", "mousemove", str(click_x), str(click_y), "click", "1"], ...)
```

**Note:** Fix requires Claude Code restart to take effect (MCP server caches Python modules).

## Related

- `tickets/find_widget_inventory_bounds_wrong.md` - Related bounds calculation issues (now fixed)
- `journals/inventory_item_clicking_wrong_item_2026-01-18.md` - Same root cause analysis
