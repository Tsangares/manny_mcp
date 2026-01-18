# Bank Withdraw Scroll + Search Fallback - Lessons Learned
**Date:** 2025-01-17

## The Problem

`BANK_WITHDRAW` silently fails when items aren't visible in the current bank view. Banks with many items require scrolling, and the command had no way to find items below the fold.

## Root Cause

The original implementation in `BankWithdrawCommand.java` only searched visible widget children via `getDynamicChildren()`. Items scrolled out of view have invalid bounds (negative Y or outside container area), causing the search to fail even though the item exists in the bank.

## Key Lessons

### 1. Widget.setScrollY() is Read-Only

**What happened:** Initial plan was to use `bankContainer.setScrollY(newValue)` to programmatically scroll.
**Why:** RuneLite's Widget API exposes `getScrollY()` but `setScrollY()` doesn't actually change the scroll position from the client side - it's meant for the game engine's internal use.
**Solution:**
```java
// BAD - setScrollY doesn't work from client code
bankContainer.setScrollY(currentScroll + 180);  // No effect

// GOOD - Use Robot.mouseWheel() with mouse over bank area
Robot robot = new Robot();
robot.mouseWheel(3);  // Positive = scroll down, negative = scroll up
```

### 2. Mouse.scroll() Doesn't Exist

**What happened:** Build failed with "cannot find symbol: method scroll(int)"
**Why:** The `Mouse` class in manny plugin doesn't have a scroll method. Only `Keyboard.zoom()` exists which uses `Robot.mouseWheel()` internally but centers mouse on canvas.
**Solution:** Use `Robot.mouseWheel()` directly after positioning mouse over bank container:
```java
// Position mouse over bank first
mouse.move(bankBounds);
Thread.sleep(30);

// Then scroll
Robot robot = new Robot();
robot.mouseWheel(3);  // Scroll down
```

### 3. ItemContainer vs Widget Children

**What happened:** Needed a way to check if item exists BEFORE attempting to scroll.
**Why:** `client.getItemContainer(InventoryID.BANK)` returns ALL items regardless of scroll position. Widget children only show items with valid screen coordinates.
**Solution:**
```java
// Check existence via ItemContainer (sees everything)
ItemContainer bank = client.getItemContainer(InventoryID.BANK);
for (Item item : bank.getItems()) {
    ItemComposition comp = client.getItemDefinition(item.getId());
    if (comp.getName().equalsIgnoreCase(itemName)) {
        // Item confirmed in bank - now scroll to find it visually
    }
}

// Widget children only show visible items with valid bounds
Widget[] children = bankContainer.getDynamicChildren();
// Items scrolled out of view have bounds.y < containerBounds.y or > containerBounds.y + height
```

### 4. Detecting Visible vs Scrolled-Out Items

**What happened:** Items exist in widget children even when scrolled out, but their bounds are invalid.
**Why:** Widget bounds are calculated relative to screen position - items above/below viewport have Y outside container area.
**Solution:**
```java
// Check both item bounds validity AND containment within viewport
Rectangle bounds = child.getBounds();
Rectangle containerBounds = bankContainer.getBounds();

boolean isVisible = bounds != null
    && bounds.x >= 0 && bounds.y >= 0
    && bounds.width > 0 && bounds.height > 0
    && bounds.y >= containerBounds.y  // Not scrolled above
    && bounds.y + bounds.height <= containerBounds.y + containerBounds.height;  // Not scrolled below
```

### 5. Finding Bank Search Button Dynamically

**What happened:** Hardcoded widget ID (786460) might be wrong or change.
**Why:** Bank interface widgets don't have well-documented IDs; need runtime discovery.
**Solution:**
```java
// Search for widget with "Search" action in bank interface (group 12)
Widget[] roots = client.getWidgetRoots();
for (Widget root : roots) {
    int groupId = root.getId() >> 16;
    if (groupId == 12) {  // Bank interface group
        // Recursively search children for widget with "Search" action
        String[] actions = widget.getActions();
        if (action.toLowerCase().contains("search")) {
            return widget.getBounds();
        }
    }
}
```

## Anti-Patterns

1. **Don't assume Widget.setScrollY() works** - It's read-only from client perspective
2. **Don't check only widget bounds != null** - Scrolled items have bounds but outside viewport
3. **Don't hardcode widget IDs without fallback** - Use action/text search as backup

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="BANK_WITHDRAW")` | See item search attempts and bounds |
| `scan_widgets(filter_text="Search")` | Find bank search button widget ID |
| `get_game_state(fields=["inventory"])` | Verify item actually withdrawn |

## Interface Gaps Identified

- [x] Plugin needs: Scroll-to-find logic for bank items (implemented)
- [x] Plugin needs: Bank search fallback (implemented)
- [ ] Mouse class could use: `scroll(int amount)` helper method (worked around with Robot)

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/BankWithdrawCommand.java` | Added scroll/search fallback, helper methods, ItemContainer check |
| `manny_src/utility/PlayerHelpers.java` | Updated constructor to pass ClientThreadHelper |

## Algorithm Summary

1. Verify item exists via `ItemContainer` (sees all items)
2. Try to find in visible widget area
3. If not visible: Reset scroll to top, then scroll down checking each position
4. If scroll fails: Click bank search button, type item name, find in filtered results
5. Max 20 scroll attempts to prevent infinite loop
