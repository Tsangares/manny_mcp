# GE_BUY Command Clicks Cancel Instead of Buy Button

**Status:** RESOLVED
**Severity:** High
**Created:** 2026-01-23
**Resolved:** 2026-01-24

## Bug Description

The `GE_BUY` command in `GEBuyCommand.java` clicks the "Cancel" button instead of the Buy button when trying to open a buy slot.

## Evidence from Logs

```
[INTERACT] Screen Click: (316, 385)
[INTERACT] Option: "Cancel" ID: -1
```

The click landed on "Cancel" (which appears when GE interface is open) instead of the Buy slot button.

## Root Cause

The `clickButtonByActionWithRetry()` method used only `mouse.move()` (Bezier curve movement) without `mouse.movePrecisely()` correction. On Wayland with `uiScale=2.0`, Bezier movement alone lands imprecisely, causing clicks to miss their targets.

## Fix Applied (2026-01-24)

Added smart click pattern to `clickButtonByActionWithRetry()` in `GEBuyCommand.java` (lines 522-531):

```java
// Click at center using smart click: move (Bezier) -> movePrecisely (correction) -> click
int clickX = bounds.x + bounds.width / 2;
int clickY = bounds.y + bounds.height / 2;

logInfo("Clicking {} at ({}, {}) using smart click", buttonName, clickX, clickY);
mouse.move(clickX, clickY);
Thread.sleep(50);
mouse.movePrecisely(clickX, clickY);  // Corrects position after Bezier
Thread.sleep(50);
mouse.click(false);
```

## Verification

Tested `GE_BUY Feather 100 5` successfully:
- All buttons clicked correctly (Buy slot, +100, +5%, Confirm, Collect)
- 100 feathers purchased (inventory: 1 → 101)
- 300 coins spent (3gp each)
- Logs showed "using smart click" for all button clicks

## Related Documentation

- Journal: `journals/ge_buy_smart_click_lessons_2026-01-24.md`
- Context fragment: `discord_bot/context_fragments/grand_exchange.md`

## Related Files

- `/home/wil/Desktop/manny/utility/commands/GEBuyCommand.java`
