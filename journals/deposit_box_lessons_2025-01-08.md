# Deposit Box Widget Clicking - Lessons Learned
**Date:** 2025-01-08

## The Problem

The deposit box interface wouldn't respond to `deposit_item()` commands. Clicks were landing in wrong positions - clicking at (284, 124) when the actual item was at (450+, 140+).

## Root Cause

**The deposit box doesn't create real widgets for items.** Unlike the regular bank interface which has clickable child widgets, the deposit box renders items directly from `InventoryID.INVENTORY` onto a canvas without creating individual widget elements.

## Key Lessons

### 1. Not All UI Elements Are Widgets

RuneLite widgets are the normal way to interact with UI, but some interfaces render content directly without creating widget children.

**Interfaces with real item widgets:**
- Regular bank (sidebar inventory at 149,0)
- Normal inventory tab
- Equipment screen

**Interfaces WITHOUT item widgets:**
- Deposit box (192,2) - items rendered from inventory container
- Some shop interfaces

**Solution:** Create "virtual widgets" by cross-referencing the inventory container with calculated grid positions.

### 2. Grid Layout Assumptions Kill You

The deposit box grid is **4 columns x 7 rows**, not 7 columns. This single wrong assumption caused all clicks to miss.

```java
// WRONG - caused clicks to miss
int cols = 7;
int col = slot % 7;  // slot 2 -> col 2

// CORRECT
int cols = 4;
int col = slot % 4;  // slot 2 -> col 2, slot 5 -> col 1
```

**Lesson:** When grid calculations fail, the FIRST thing to verify is the column/row count. Take a screenshot and count.

### 3. Coordinate Systems Are Tricky

Multiple coordinate systems at play:
1. **Widget-local** - relative to widget's top-left
2. **Container-local** - relative to parent container
3. **Canvas** - relative to game canvas
4. **Screen** - absolute screen position

The virtual widget bounds were being calculated in container-local space but mouse clicks need screen-space coordinates.

**Fix pattern:**
```java
// Get container's screen position
Rectangle containerBounds = depositBoxWidget.getBounds();

// Calculate item position relative to container
int localX = gridStartX + (col * cellWidth);
int localY = gridStartY + (row * cellHeight);

// Convert to screen coordinates
int screenX = containerBounds.x + localX;
int screenY = containerBounds.y + localY;
```

### 4. Debug Incrementally

The full chain from "find item" to "deposit item" has many steps:
1. Find item in inventory data
2. Calculate grid position
3. Convert to screen coordinates
4. Right-click at position
5. Find "Deposit-All" in menu
6. Click menu option

**Don't debug the whole chain at once.** Add logging at each step:
- Log the calculated position
- Log what menu entries were found
- Log which entry was clicked

When clicks land on "Cancel" instead of "Deposit-All", the position is wrong.

### 5. Test Multiple Slots

The lobsters (slots 9+) worked but fishing nets (slots 2-5) didn't. Different slots exercise different parts of the grid calculation:

| Slot | Col (4-col) | Row | Notes |
|------|-------------|-----|-------|
| 0 | 0 | 0 | Top-left corner |
| 3 | 3 | 0 | End of first row |
| 4 | 0 | 1 | Start of second row |
| 9 | 1 | 2 | Middle area |

**Lesson:** Test at least slots 0, 3, 4, and a middle slot to verify grid math.

### 6. UI Scaling Complicates Everything

RuneLite runs with `-Dsun.java2d.uiScale=2.0`. This means:
- Widget bounds might be in logical or physical pixels
- Mouse events might need different coordinates
- The relationship depends on stretched mode settings

When coordinates are consistently off by a factor, check UI scaling.

## The Fix

In `ScanWidgetsCommand.java`, the virtual widget grid calculation:

```java
// Fixed grid layout
int cols = 4;  // Was incorrectly 7
int col = slot % cols;
int row = slot / cols;

// Proper cell dimensions
int cellWidth = 42;
int cellHeight = 36;
int startX = containerBounds.x + gridOffsetX;
int startY = containerBounds.y + gridOffsetY;

int itemX = startX + (col * cellWidth) + (cellWidth / 2);
int itemY = startY + (row * cellHeight) + (cellHeight / 2);
```

## Anti-Patterns to Avoid

1. **Don't assume all interfaces have item widgets** - Check if items are rendered from containers
2. **Don't hardcode grid dimensions** - Verify visually before coding
3. **Don't debug end-to-end** - Log intermediate values
4. **Don't test only one slot** - Test corners and middle of grid
5. **Don't ignore coordinate systems** - Know which space you're in

## Commands for Debugging Widget Issues

```python
# Find what widgets exist
scan_widgets(filter_text="lobster")
find_widget(text="Raw lobster")

# Check inventory state
get_game_state()  # Shows inventory items with slot numbers

# Visual verification
get_screenshot()
analyze_screenshot(prompt="Where are the items in the deposit box grid?")

# Check plugin logs
get_logs(level="DEBUG", grep="click")
```

## Files Modified

| File | Change |
|------|--------|
| `ScanWidgetsCommand.java` | Fixed grid cols from 7 to 4, added virtual widget creation |
| `BankDepositItemCommand.java` | Updated grid calculation to match |

## Testing Checklist for Future Widget Work

- [ ] Verify the interface creates real widgets (use scan_widgets)
- [ ] If no widgets, check what data source drives the display
- [ ] Count grid columns/rows visually before coding
- [ ] Test multiple grid positions (corners + middle)
- [ ] Log calculated vs actual click positions
- [ ] Verify menu entries found match expectations
