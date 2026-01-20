# Deposit Box Widget Click Issues

**Date:** 2025-01-08
**Problem:** BANK_DEPOSIT_ITEM command fails to deposit items when deposit box is open

## The Core Problem

The deposit box interface (widget group 192, child 2) **does not create individual item widgets**. Items are rendered directly from the `InventoryID.INVENTORY` container onto the deposit box canvas without creating clickable child widgets.

This is different from:
- Regular bank interface - has item widgets in sidebar inventory (149, 0)
- Regular inventory tab - has item widgets with bounds

## What We Tried

### 1. Virtual Widgets in ScanWidgetsCommand

Created "synthetic" widget entries by cross-referencing inventory items with calculated grid positions:

```java
// Grid layout: 7 columns x 4 rows
int gridBaseX = containerBounds.x + 170;
int gridBaseY = containerBounds.y + 15;
int cellWidth = 42;
int cellHeight = 36;

int col = slot % 7;
int row = slot / 7;
int itemX = gridBaseX + (col * cellWidth) + 18;  // center offset
int itemY = gridBaseY + (row * cellHeight) + 16;
```

**Problem:** These coordinates are in widget-local space, not screen space. The deposit box container itself has a position, and with UI scaling, the relationship is complex.

### 2. BankDepositItemCommand Grid Calculation

Same grid calculation approach in the command handler:

```java
int gridBaseX = containerBounds.x + 170;
int gridBaseY = containerBounds.y + 15;
// ... calculate position ...
itemBounds[0] = new Rectangle(itemX - 16, itemY - 16, 32, 32);
```

**Problem:** Click landed at (284, 124) - in the equipment slot area, not on the lobsters which are visually around (450-700, 130-500).

### 3. send_input MCP Tool Bug (FIXED)

Found and fixed a bug where coordinates were comma-separated:
```python
# Before (broken):
command = f"MOUSE_MOVE {x},{y}\nMOUSE_CLICK {button_name}"

# After (fixed):
command = f"MOUSE_MOVE {x} {y}\nMOUSE_CLICK {button_name}"
```

This was causing `NumberFormatException: For input string: "564,305"`.

### 4. Direct Coordinate Clicking

Tried clicking at various coordinates based on visual estimation:
- (287, 122) - no deposit
- (463, 182) - no deposit
- (500, 360) - no deposit
- (558, 359) - no deposit

None of these deposited items, suggesting either:
- Coordinates still wrong after scaling
- Right-click menu not appearing properly
- Menu entries not matching expected format

## Root Cause Analysis

### UI Scaling Complexity

RuneLite runs with `-Dsun.java2d.uiScale=2.0`. This means:
- Widget bounds are reported in "logical" pixels
- Mouse clicks may need to be in "physical" pixels (or vice versa)
- The relationship depends on whether stretched mode is enabled

### Widget Coordinate Systems

Multiple coordinate systems at play:
1. **Widget-local coordinates** - relative to widget's top-left
2. **Canvas coordinates** - relative to game canvas
3. **Window coordinates** - relative to RuneLite window
4. **Screen coordinates** - absolute screen position

The deposit box container reports bounds like `(83, 53, 706, 510)` but this may be in one coordinate system while mouse clicks use another.

### Menu Entry Mismatch

Even when right-click opens a menu, the log shows:
```
Available menu entries (1 total):
```

Only 1 entry found, and it's not "Deposit-All". This suggests the click isn't landing on an item at all - it's hitting empty space or a non-item widget.

## Possible Solutions

### Solution 1: Use Debug Overlay to Find Correct Offsets

Add extensive logging to capture:
- Container bounds at click time
- Calculated item position
- Actual mouse position sent
- What the menu shows

Compare visually to determine the offset error.

### Solution 2: Use Sidebar Inventory Instead

When deposit box is open, the sidebar still shows inventory with **real widgets** that have correct bounds:
- Widget (149, 0) children have `itemId` set
- These widgets have proper `getBounds()` that work for clicking

Modify `BankDepositItemCommand` to always use sidebar inventory widgets when deposit box is open, rather than calculating positions in the deposit box container.

### Solution 3: Empirical Calibration

Take screenshots, measure actual pixel positions of items, and compare to calculated positions. Derive a correction factor:
```java
// If calculated = (284, 124) but actual = (450, 180)
int offsetX = 166;  // correction
int offsetY = 56;   // correction
```

### Solution 4: Use Widget Actions Instead of Coordinates

Instead of clicking at coordinates, use RuneLite's menu injection:
```java
// Inject menu entry directly
client.createMenuEntry(-1)
    .setOption("Deposit-All")
    .setTarget("<col=ff9040>Raw lobster</col>")
    .setType(MenuAction.CC_OP)
    .setParam0(slot)
    .setParam1(widgetId)
    .onClick(...)
```

This bypasses coordinate calculation entirely but requires understanding the correct MenuAction type and parameters.

### Solution 5: Click "Deposit inventory" Button

The deposit box has a "Deposit inventory" button that deposits ALL items at once. For cases where we want to deposit everything:
```java
// Find and click the "Deposit inventory" button widget
Widget depositAllButton = client.getWidget(192, 4);  // or similar
```

This is simpler but less granular than per-item deposit.

## Recommended Next Steps

1. **Add debug logging** to BankDepositItemCommand to print:
   - `containerBounds` value
   - Calculated `(itemX, itemY)` before and after any transformations
   - The actual Rectangle being clicked

2. **Compare with screenshot** - overlay calculated positions on screenshot to see where they actually land

3. **Try sidebar inventory approach** - this is likely the most reliable since those widgets have proven bounds

4. **Test without UI scaling** - temporarily remove `-Dsun.java2d.uiScale=2.0` to see if coordinates work correctly at 1x scale

## Files Involved

| File | Purpose |
|------|---------|
| `manny_src/utility/commands/BankDepositItemCommand.java` | Deposit item command handler |
| `manny_src/utility/commands/ScanWidgetsCommand.java` | Virtual widget creation for deposit box |
| `manny-mcp/mcptools/tools/commands.py` | send_input MCP tool (coordinate formatting) |
| `manny_src/utility/PlayerHelpers.java` | `clickMenuEntrySafe()` method |

## Key Discovery: Widget-Local vs Screen Coordinates

**From widget scan output (`/tmp/manny_widgets.json`):**
```json
{
  "isVirtualDepositSlot": true,
  "slotIndex": 8,
  "itemName": "Raw lobster",
  "bounds": {"x": 269, "y": 106, "width": 36, "height": 32},
  "actions": ["Deposit-1", "Deposit-5", "Deposit-10", "Deposit-X", "Deposit-All"],
  "group": 192,
  "child": 2
}
```

**BankDepositItemCommand clicked at:** (284, 124) - matches widget bounds center (287, 122)

**But visually**, the first lobster is at approximately (450, 140) in the screenshot!

**Root cause confirmed:** The virtual widget bounds are in **container-local coordinates**, but mouse clicks need **screen coordinates**. The deposit box container (192:2) has its own position that needs to be added.

**The fix:** When calculating click position, must add the container's screen position:
```java
// Current (broken):
int clickX = gridBaseX + (col * cellWidth) + itemWidth/2;

// Correct:
Rectangle containerScreenPos = depositBoxContainer.getBounds();  // screen coords
int clickX = containerScreenPos.x + gridOffsetX + (col * cellWidth) + itemWidth/2;
```

## Lessons Learned

1. **Widget absence is a real thing** - Not all UI elements create widgets. Some are rendered directly from data.

2. **Coordinate systems multiply** - UI scaling, stretched mode, and widget hierarchies create multiple coordinate transformations that must all be correct.

3. **Test incrementally** - Should have added logging to verify each step (item found? bounds correct? click position correct? menu opened? entries found?) rather than debugging the whole chain at once.

4. **Fallback strategies matter** - Having multiple approaches (deposit box coords vs sidebar widgets vs deposit-all button) provides resilience.
