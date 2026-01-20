# Shop Interface Widget Click Issue

**Date:** 2025-01-07
**Shop:** Gerrant's Fishy Business (Port Sarim)
**Item:** Small fishing net
**Widget ID:** 19660816

## Problem Summary

Attempting to purchase items from shop interfaces using `CLICK_WIDGET` and `send_input` commands fails to complete the purchase. The widget clicks are registered, but the item is not added to inventory.

## Reproduction Steps

1. Open shop interface (Gerrant's Fishy Business)
2. Scan widgets to find item: `find_widget(text="Small fishing net")`
   - Returns widget_id: 19660816
3. Attempt to click quantity button: `send_command("CLICK_WIDGET 19660809")` (quantity "1")
   - Response: Success
4. Attempt to click item: `send_command("CLICK_WIDGET 19660816")`
   - Response: Success, "Widget clicked successfully"
5. Check inventory: Item not present
6. Alternative attempt using direct mouse input: `send_input(click, x=160, y=197, button=1)`
   - Response: Success
7. Check inventory again: Still no item

## Observed Behavior

- Widget click commands return success status
- Chat log shows "Price of Small fishing net: GE average 191 HA value 3" - indicates a VALUE CHECK was triggered instead of BUY
- Shop stock increased from 99 to 100 (should decrease on purchase)
- No "You buy a small fishing net" message in chat
- Inventory unchanged after all attempts

## Widget Details

**Small fishing net widget (19660816):**
```json
{
  "widget_id": 19660816,
  "text": "<col=ff9040>Small fishing net</col>",
  "bounds": {
    "x": 77,
    "y": 64,
    "width": 36,
    "height": 32
  },
  "actions": [
    "Value",
    "Buy 1",
    "Buy 5",
    "Buy 10",
    "Buy 50",
    "Examine"
  ]
}
```

**Quantity button "1" (19660809):**
```json
{
  "widget_id": 19660809,
  "text": "1",
  "bounds": {
    "x": null,
    "y": null,
    "width": null,
    "height": null
  },
  "actions": []
}
```

## Attempts Made

### Attempt 1: Direct widget click
```python
send_command("CLICK_WIDGET 19660816")
```
**Result:** Value check triggered instead of purchase

### Attempt 2: Quantity button + item click
```python
send_command("CLICK_WIDGET 19660809")  # Click "1" button
send_command("CLICK_WIDGET 19660816")  # Click fishing net
```
**Result:** Value check triggered, no purchase

### Attempt 3: Right-click
```python
send_input(input_type="click", x=95, y=80, button=3)
find_widget(text="Buy 1")  # Scan for context menu
```
**Result:** No "Buy 1" widget found (context menu didn't appear or widgets not scanned correctly)

### Attempt 4: Direct left-click coordinates
```python
send_input(input_type="click", x=160, y=197, button=1)
```
**Result:** No change in inventory

## Game State Before/After

**Inventory before:** 4/28 slots used
- Coins (850)
- Fly fishing rod
- Harpoon
- Lobster pot

**Inventory after all attempts:** Unchanged

**Coins:** 850 (unchanged - purchase didn't deduct cost)

## Command Response Log

```json
{
  "timestamp": 1767845847263,
  "command": "CLICK_WIDGET",
  "status": "success",
  "result": {
    "widget_id": 19660816,
    "message": "Widget clicked successfully"
  }
}
```

## Screenshots

- Before: `/tmp/runelite_screenshot_1767845824.png`
- After: `/tmp/runelite_screenshot_1767845877.png`

Chat shows: "Price of Small fishing net: GE average 191 HA value 3"

## Hypothesis

The `CLICK_WIDGET` command may be:
1. Triggering the wrong action (Value instead of Buy 1)
2. Not properly handling shop interface widgets
3. Missing a required interaction sequence (quantity selection state)
4. Clicking at wrong coordinates within the widget bounds

OSRS shop mechanics typically require:
1. Select quantity (1, 5, 10, 50 buttons)
2. Click item to purchase

The quantity button click may not be registering properly, leaving the shop in "Value check" mode.

## Possible Solutions to Investigate

1. Check if `CLICK_WIDGET` implementation handles action selection for multi-action widgets
2. Verify widget click coordinates are centered on the widget
3. Check if shop state needs to be explicitly set before item click
4. Consider if a menu entry needs to be manually constructed
5. Test if `INTERACT_WIDGET` command exists with action parameter
6. Check PlayerHelpers.java for shop-specific interaction handlers

## Related Code

Likely in `manny_src/utility/PlayerHelpers.java`:
- Search for `CLICK_WIDGET` command handler
- Check if shop-specific logic exists
- Review widget interaction implementation

## Status

**UNRESOLVED** - Unable to purchase items from shop interface using current MCP tools.

## Next Steps

1. Read PlayerHelpers.java to find CLICK_WIDGET implementation
2. Check if there's a shop-specific command (e.g., BUY_ITEM)
3. Test with other shop interfaces to see if issue is universal
4. Consider adding SHOP_BUY command to plugin if missing
