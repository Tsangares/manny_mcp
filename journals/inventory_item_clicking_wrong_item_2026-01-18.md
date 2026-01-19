# Inventory Item Clicking Wrong Item - Lessons Learned
**Date:** 2026-01-18

## The Problem

`find_and_click_widget("Bronze dagger")` consistently equipped the Bronze pickaxe instead of the Bronze dagger. Despite finding the correct item, clicks landed on the wrong inventory slot.

## Root Cause

**Two separate bugs compounding:**

1. **ScanWidgetsCommand.java** - Inventory items (group 149) returned the container's bounds instead of calculating each item's grid position. All inventory items shared the same bounds (560, 282), regardless of their actual slot.

2. **find_and_click_widget (routine.py)** - Even with correct bounds, it passed `CLICK_WIDGET {container_id} "{action}"` to Java, which searched for the FIRST child widget with that action - finding Bronze pickaxe (slot 7) before Bronze dagger (slot 8).

3. **Java Mouse.click() doesn't register** - Even when switching to `CLICK_AT` with correct coordinates, the Java-based click methods moved the mouse but didn't register clicks. Only `xdotool` worked.

## Key Lessons

### 1. Widget Bounds for Container Items Need Grid Calculation

**What happened:** `find_widget("Bronze dagger")` returned bounds at (560, 282) for ALL inventory items.
**Why:** Inventory widgets are dynamic children of a container (9764864). The Java `widget.getBounds()` returns the container's bounds, not individual slot positions.

**Solution (ScanWidgetsCommand.java:497-522):**
```java
// BAD - returns container bounds for all items
java.awt.Rectangle bounds = widget.getBounds();

// GOOD - calculate grid position from slot index
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

### 2. Don't Search by Action When Container Has Multiple Matching Items

**What happened:** `CLICK_WIDGET 9764864 "Wield"` searched children for first "Wield" action, finding Bronze pickaxe before dagger.
**Why:** The Java click command re-searches children by action, ignoring the bounds we already found.

**Solution (routine.py:1420-1438):**
```python
# BAD - Java re-searches and finds wrong item
click_command = f'CLICK_WIDGET {widget_id} "{action}"'

# GOOD - click at the bounds we already found
click_x = bounds["x"] + bounds["width"] // 2
click_y = bounds["y"] + bounds["height"] // 2
subprocess.run(["xdotool", "mousemove", str(click_x), str(click_y), "click", "1"],
               env={**os.environ, "DISPLAY": display})
```

### 3. Java Mouse.click() Doesn't Register - Use xdotool

**What happened:** `CLICK_AT`, `MOUSE_CLICK`, and `send_input(click)` all moved the mouse correctly (tooltips confirmed hover) but clicks never registered.
**Why:** Unknown - possibly Java AWT event generation issue with Wayland/XWayland or RuneLite's input handling.

**Solution:** Use `xdotool` for clicking:
```bash
DISPLAY=:2 xdotool mousemove 704 262 click 1
```

## Anti-Patterns

1. **Don't** rely on `CLICK_WIDGET {id} "{action}"` when multiple items have the same action - it finds the first match, not your target
2. **Don't** trust Java mouse methods for actual clicking - verify with xdotool if clicks aren't registering
3. **Don't** assume widget.getBounds() returns correct positions for container children - inventory, deposit box, bank all need grid calculation

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `find_widget(text="item")` | Check returned bounds - if multiple items have same bounds, grid calc is broken |
| `get_game_state(fields=["inventory_full"])` | Get actual slot numbers for items |
| `get_screenshot()` | Verify mouse position (check tooltip) |
| `DISPLAY=:2 xdotool mousemove X Y click 1` | Test if clicking works at all |

## Interface Gaps Identified

- [x] **ScanWidgetsCommand.java** - Added inventory grid position calculation
- [x] **routine.py (find_and_click_widget)** - Use xdotool instead of broken Java click
- [ ] **Java Mouse.click()** - Fundamental issue - clicks don't register (workaround: xdotool)
- [ ] **CLICK_AT command** - Should use xdotool internally instead of Mouse.click()

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/ScanWidgetsCommand.java` | Added inventory (group 149) grid position calculation based on slot index |
| `mcptools/tools/routine.py` | `find_and_click_widget` now uses xdotool for clicking when bounds are available |

## Time Cost

~60 minutes debugging. Key insight came from testing `xdotool` directly after all Java click methods failed despite correct mouse positioning.
