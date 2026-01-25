# GE Buy Command - Smart Click and Widget Discovery Lessons
**Date:** 2026-01-24

## The Problem

GE_BUY command was failing at multiple stages: finding empty slots incorrectly, clicking wrong widget for search results (chatbox instead of GE), and button clicks (quantity, price, confirm, collect) not registering despite correct coordinates.

## Root Cause

Three distinct issues:

1. **`findEmptySlot()`** returned slots when not on the slots overview interface - it didn't verify the current view
2. **`selectSearchResult()`** used widget (162, 0) which includes the chatbox, not (162, 51) which is the actual GE search results
3. **`clickButtonByActionWithRetry()`** used only `mouse.move()` (Bezier curve) which isn't accurate enough on Wayland with UI scaling - needed `mouse.movePrecisely()` correction

## Key Lessons

### 1. Smart Click Pattern is Essential for Wayland/UI Scaling

**What happened:** Button clicks found correct coordinates but clicks landed elsewhere. Only 1 feather was bought instead of 100 because +100 button click didn't register.

**Why:** `mouse.move()` uses Bezier curves for natural movement but lands imprecisely. On Wayland with `uiScale=2.0`, small errors are magnified.

**Solution:**
```java
// BAD - Bezier movement alone is imprecise
mouse.move(clickX, clickY);
Thread.sleep(50);
mouse.click(false);  // May miss the target

// GOOD - Smart click: Bezier + precision correction + click
mouse.move(clickX, clickY);
Thread.sleep(50);
mouse.movePrecisely(clickX, clickY);  // Corrects position
Thread.sleep(50);
mouse.click(false);  // Now accurate
```

### 2. Widget Group 162 is the Chatbox, NOT GE Search Results

**What happened:** Search result clicking was hitting the chatbox (y=458) instead of GE results (y=367). Text typed into search was appearing in chat.

**Why:** Widget (162, 0) is the chatbox parent. GE search results are in child 51 specifically.

**Solution:**
```java
// BAD - Gets chatbox which overlaps GE area
Widget searchResults = client.getWidget(162, 0);

// GOOD - Gets actual GE search results
Widget searchResults = client.getWidget(162, 51);
```

### 3. Verify Interface State Before Acting

**What happened:** `findEmptySlot()` returned slot 1 even when viewing an active offer detail screen, causing "Unexpected offer state: EMPTY" errors.

**Why:** The API's `GrandExchangeOffers` returns slot states regardless of what interface is displayed. Code assumed slots overview was visible.

**Solution:**
```java
// BAD - Assumes we're on slots overview
GrandExchangeOffer[] offers = client.getGrandExchangeOffers();
// Returns EMPTY for slot 1 even if we're viewing slot 2's details

// GOOD - First verify the interface state
boolean onSlotsOverview = false;
for (int i = 0; i < 8; i++) {
    Widget slotWidget = client.getWidget(slotWidgetId);
    if (hasCreateOfferAction(slotWidget)) {  // "Create Buy offer" / "Create Sell offer"
        onSlotsOverview = true;
        break;
    }
}
if (!onSlotsOverview) return 0;  // Not on overview, can't trust slot data
```

### 4. Logs Say "Success" But Action Didn't Happen

**What happened:** Logs showed "Command succeeded" but only 1 feather was in inventory, not 100.

**Why:** The code structure returns `true` after attempting the click without verifying the click had an effect. Imprecise clicks were "successful" attempts that missed.

**Debugging technique:** Compare expected vs actual game state. Logs claiming success mean nothing if inventory doesn't change as expected.

## Anti-Patterns

1. **Don't** trust `mouse.move()` alone for precision - always follow with `mouse.movePrecisely()` for important clicks
2. **Don't** assume widget child 0 contains what you want - scan widgets to discover the actual structure
3. **Don't** trust API state without verifying the visible interface matches your assumptions
4. **Don't** trust "Command succeeded" logs - verify with actual game state

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `find_widget(text="Feather")` | Find which widget contains search results (revealed y=458 = chatbox) |
| `scan_widgets(group=162)` | Enumerate chatbox structure |
| `scan_widgets(group=465)` | Check if GE interface is actually open |
| `get_game_state(fields=["inventory_full"])` | Verify actual quantities after "successful" commands |
| `grep "using smart click" logs` | Verify new code is loaded after build |

## Interface Gaps Identified

- [x] Plugin needs: Smart click pattern in `clickButtonByActionWithRetry()` - **FIXED**
- [x] Plugin needs: Interface verification in `findEmptySlot()` - **FIXED**
- [x] Plugin needs: Correct widget ID for search results - **FIXED**
- [ ] CLAUDE.md needs: Document smart click as mandatory pattern for all UI clicks

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/GEBuyCommand.java` | Added smart click to `clickButtonByActionWithRetry()` (lines 527-531) |
| `manny_src/utility/commands/GEBuyCommand.java` | Fixed search widget from (162,0) to (162,51) in `selectSearchResult()` |
| `manny_src/utility/commands/GEBuyCommand.java` | Added `hasCreateOfferAction()` and interface verification in `findEmptySlot()` |
| `manny_src/utility/commands/GESellCommand.java` | Same `findEmptySlot()` fix applied |

## Time Spent

- Initial diagnosis of slot detection: ~15 min
- Discovering chatbox vs GE widget issue: ~20 min
- Realizing smart click was needed for all buttons: ~30 min
- Total debugging session: ~1.5 hours
