# Bank Commands & Display Targeting Issues

**Date:** 2026-01-29
**Context:** Testing and fixing bank commands, discovered display targeting bug

## Summary

Tested all 8 bank commands. Found 3 broken widget IDs and a fundamental display targeting issue with Mouse/Robot classes when using gamescope displays.

## Fixes Applied

### 1. BANK_DEPOSIT_ALL - Wrong Widget ID
**File:** `GameEngine.java:111`
```java
// BEFORE (broken)
private static final int DEPOSIT_INVENTORY_BUTTON = 786476;

// AFTER (fixed)
private static final int DEPOSIT_INVENTORY_BUTTON = 786473;
```
**Root cause:** Widget IDs changed, constant was stale.

### 2. BANK_DEPOSIT_EQUIPMENT - Wrong Widget ID
**File:** `BankDepositEquipmentCommand.java:18`
```java
// BEFORE (broken)
private static final int BANK_DEPOSIT_EQUIPMENT_WIDGET = 786478;

// AFTER (fixed)
private static final int BANK_DEPOSIT_EQUIPMENT_WIDGET = 786475;
```

### 3. BANK_CHECK - Only Accepted Item IDs
**File:** `BankCheckCommand.java`

Updated to accept both item IDs and names:
```python
# Now works with both:
BANK_CHECK 379        # By item ID
BANK_CHECK Lobster    # By item name
BANK_CHECK Bronze_bar # Underscores converted to spaces
```

## RESOLVED: Display Targeting Bug (2026-02-03)

### Original Symptom
`BANK_WITHDRAW` finds the correct item bounds but clicks the wrong item:
```
[BANK_WITHDRAW] Item 'Rune pickaxe' found at bounds=(217,200,36,32)
[BANK_WITHDRAW] clicking at center (235,216)
[BANK_WITHDRAW] Mouse now at (237, 276)  # <-- Y is wrong!
Option: "Withdraw-1" | Target: "Iron kiteshield"  # Clicked wrong item
```

### Root Cause
The `Mouse` class and `Robot.mouseWheel()` target the **user's main display** instead of the **gamescope display (:2)** where RuneLite is running.

When RuneLite runs on gamescope display :2:
- Widget bounds are correct (in gamescope coordinate space)
- `mouse.move(x, y)` sends events to the wrong X display
- Click lands on whatever is at those coordinates on the main display

### Evidence
The Y coordinate shift (216 → 276) is consistent with display offset between gamescope and main display.

### Affected Commands
- `BANK_WITHDRAW` - uses mouse.move() for item clicking
- Any command using `Robot.mouseWheel()` for scrolling
- Any command using raw mouse coordinates

### Commands That Work
- `BANK_DEPOSIT_ALL` - uses `widgetClickHelper.clickWidget(id)`
- `BANK_DEPOSIT_EQUIPMENT` - uses `widgetClickHelper.clickWidget(id)`
- `click_widget(id)` MCP tool - uses internal widget clicking

### Workaround
Use `find_widget()` + manual interaction, or commands that use widget-based clicking instead of mouse coordinates.

### FIX APPLIED (2026-02-03)

The solution was to bypass the system window manager entirely by dispatching events directly to the RuneLite canvas instead of using Robot.

**Mouse.java - Added scroll() method:**
```java
public void scroll(int x, int y, int amount) throws InterruptedException {
    Canvas canvas = client.getCanvas();
    // Dispatch MouseWheelEvent directly to canvas - bypasses window manager
    java.awt.event.MouseWheelEvent wheelEvent = new java.awt.event.MouseWheelEvent(
        canvas,
        java.awt.event.MouseWheelEvent.MOUSE_WHEEL,
        System.currentTimeMillis(),
        0,  // modifiers
        x, y,
        0,  // clickCount
        false,  // popupTrigger
        java.awt.event.MouseWheelEvent.WHEEL_UNIT_SCROLL,
        3,  // scrollAmount
        amount  // wheelRotation
    );
    canvas.dispatchEvent(wheelEvent);
}
```

**Keyboard.java - Updated zoom() method:**
Same pattern - dispatches MouseWheelEvent directly to canvas instead of using Robot.mouseWheel().

**BankWithdrawCommand.java - Fixed visibility check:**
Changed from checking entire item bounds to checking item CENTER:
```java
int itemCenterX = bounds.x + bounds.width / 2;
int itemCenterY = bounds.y + bounds.height / 2;
boolean centerVisibleX = itemCenterX >= visibleMinX && itemCenterX <= visibleMaxX;
boolean centerVisibleY = itemCenterY >= visibleMinY && itemCenterY <= visibleMaxY;
```

**Why this works:**
- Canvas.dispatchEvent() sends events directly to RuneLite's AWT event queue
- This bypasses the X11 window manager completely
- Works regardless of which display has focus
- No DISPLAY environment variable manipulation needed

## Discovery Method

Used `find_widget(text="...")` to discover correct widget IDs:
```python
find_widget(text="Deposit")
# Returns: 786473 = "Deposit inventory", 786475 = "Deposit worn items"
```

Then compared against constants in source code to find mismatches.

## Test Results After Fixes

| Command | Status |
|---------|--------|
| BANK_OPEN | PASS |
| BANK_CLOSE | PASS |
| BANK_DEPOSIT_ITEM | PASS |
| BANK_DEPOSIT_ALL | PASS (fixed) |
| BANK_DEPOSIT_EQUIPMENT | PASS (fixed) |
| BANK_CHECK | PASS (fixed - supports names) |
| SCAN_BANK | PASS |
| BANK_WITHDRAW | PASS (fixed 2026-02-03 - canvas-direct scroll, center visibility) |

## KNOWN ISSUE: CAST_SPELL_ON_INVENTORY_ITEM F-key Problems

### Symptom
`CAST_SPELL_ON_INVENTORY_ITEM Superheat_Item Iron_ore` opens the Quest tab instead of Magic tab.

### Root Cause
The command used `keyboard.pressKey(KEY_F6)` but F6 opens Quest tab (not Magic) on this system.

### Fix Applied (2026-02-03)
Changed to use `playerHelpers.openMagic()` which uses widget-based clicking:
```java
// BEFORE
log.info("[CAST_SPELL_ON_INVENTORY_ITEM] Opening Magic tab (F6)");
keyboard.pressKey(KEY_F6);

// AFTER
log.info("[CAST_SPELL_ON_INVENTORY_ITEM] Opening Magic tab");
if (!playerHelpers.openMagic()) { ... }
```

Also fixed `openInventory()` usage for the inventory tab step.

### Note
The `openMagic()` method itself still uses KEY_F6 internally via `switchToTab()`. This may need further investigation if the F-key mapping is truly different on this system.

### Workaround
Use manual CLICK_AT approach:
```python
# 1. Click magic tab icon
CLICK_AT 737 202

# 2. Find and click Superheat Item spell
find_widget(text="Superheat")  # Returns bounds
CLICK_AT <spell_center_x> <spell_center_y>

# 3. Find and click iron ore in inventory
find_widget(text="Iron ore")  # Returns bounds
CLICK_AT <ore_center_x> <ore_center_y>
```

## Key Lesson

**Widget IDs change.** Use `find_widget(action="...")` to discover current IDs rather than assuming hardcoded constants are correct. When clicks land on wrong targets, check if mouse events are going to the correct display.
