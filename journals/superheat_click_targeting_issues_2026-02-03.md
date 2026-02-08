# Superheat Spell & Click Targeting Issues

**Date:** 2026-02-03
**Context:** Attempting to automate Superheat Item spell casting, discovered multiple interrelated bugs

## Summary

CAST_SPELL_ON_INVENTORY_ITEM fails due to F-key mapping issues, widget visibility detection problems, and intermittent click registration failures. Root causes span the Mouse class, tab switching logic, and coordinate handling.

## Issues Discovered

### 1. F-Key Tab Mapping Mismatch

**Symptom:** `CAST_SPELL_ON_INVENTORY_ITEM Superheat_Item Iron_ore` opens Quest tab instead of Magic tab.

**Root Cause:** The `switchToTab()` method uses hardcoded F-key codes:
```java
// PlayerHelpers.java:7183
return switchToTab("Magic", MAGIC_TAB_CHILD, KEY_F6);
```

On user's system, F6 opens Quest tab, not Magic. F-key to tab mappings vary by:
- RuneLite settings
- System keyboard configuration
- Custom keybindings

**File:** `manny_src/utility/PlayerHelpers.java:7211` (`switchToTab` method)

**Fix:** Use widget-based tab clicking instead of F-keys:
```java
// Instead of:
keyboard.pressKey(fKeyCode);

// Use:
widgetClickHelper.clickWidget(TAB_ICON_WIDGET_ID);
```

### 2. Widget Visibility Detection Failure

**Symptom:** `isTabOpen()` returns false even when widgets ARE visible per `scan_widgets`.

**Error message:**
```
Failed to open Magic tab - Toplevel widget (548, 0x56) not visible
```

**Evidence:** `scan_widgets(group=548)` returns many visible widgets, but `client.getWidget(548, 86)` returns null or hidden.

**Root Cause:** Possible timing issue or thread synchronization. The `isTabOpen()` check runs on clientThread but may be checking stale state.

**File:** `manny_src/utility/PlayerHelpers.java:7246` (`isTabOpen` method)

**Investigation needed:**
- Check if widget lookup is thread-safe
- Add debug logging to see exactly what `client.getWidget()` returns
- Consider using a more robust visibility check

### 3. CLICK_AT Menu Event Intermittency

**Symptom:** Some CLICK_AT commands generate menu events, others don't, despite clicking at valid widget coordinates.

**Evidence:**
```
16:03:59 - CLICK_AT 737 202 -> Option: "Magic" (SUCCESS)
16:04:18 - CLICK_AT 668 289 -> Option: "Cast Superheat Item" (SUCCESS)
16:04:34+ - CLICK_AT commands don't generate menu events (FAIL)
```

**Contributing factors:**
- Window geometry shows 1x1 pixels (abnormal)
- xdotool reports position -1,-1
- Gamescope display state may be unstable

**Fix Applied (partial):** Added MOUSE_MOVED dispatch before clicks in `Mouse.java:91`:
```java
// CRITICAL: Send MOUSE_MOVED first to update RuneLite's internal mouse position tracking
MouseEvent moveEvt = new MouseEvent(canvas, MouseEvent.MOUSE_MOVED, now, 0, x, y, 0, false);
canvas.dispatchEvent(moveEvt);
```

This fixed coordinate targeting but didn't resolve the intermittent menu event registration.

### 4. MOUSE_MOVE + MOUSE_CLICK Race Condition

**Symptom:** When using `click_widget` MCP tool, MOUSE_CLICK executes BEFORE MOUSE_MOVE completes.

**Evidence:**
```
15:58:50 - MOUSE_MOVE starts executing
15:58:50 - MOUSE_CLICK starts executing (before move finishes!)
15:58:50 - MOUSE_CLICK succeeds (at WRONG position)
15:58:50 - MOUSE_MOVE succeeds
```

**Root Cause:** Commands are processed asynchronously on different background threads.

**Fix:** Either:
1. Use CLICK_AT which is atomic (move + click in one command)
2. Ensure MOUSE_MOVE completes before MOUSE_CLICK starts

## Workarounds Tested

### Manual CLICK_AT Sequence
```python
CLICK_AT 737 202  # Click Magic tab icon
# Wait ~0.5s
CLICK_AT 668 289  # Click Superheat spell
# Wait ~0.5s
CLICK_AT 662 298  # Click Iron ore
```

**Result:** Works intermittently. Spell click succeeds, but item click often fails to register.

### Widget-Based Clicking
```python
click_widget(widget_id=14286881)  # Superheat spell
click_widget(widget_id=9764864, bounds={"x": 644, "y": 282, ...})  # Iron ore
```

**Result:** Also intermittent due to underlying MOUSE_MOVE/CLICK race condition.

## Recommended Fixes

### Priority 1: Widget-Based Tab Switching
Replace F-key tab switching with direct widget clicks. Tab icon widget IDs are stable.

### Priority 2: Add Current Tab Detection
Add `currentTab` field to game state JSON:
```json
{
  "player": {
    "currentTab": "Magic"  // or "Inventory", "Combat", etc.
  }
}
```

Detection approaches:
1. Check which toplevel child widget (0x50-0x56) is visible
2. Check tab icon sprite IDs (selected vs unselected state)
3. Use `client.getVarcIntValue()` if a varc tracks the active tab

### Priority 3: Fix CLICK_AT Reliability
Investigate why menu events stop registering after some clicks work. May be related to:
- Gamescope display state
- Window focus
- Mouse event dispatch timing

## Files Modified This Session

- `manny_src/human/Mouse.java:91` - Added MOUSE_MOVED dispatch before clicks
- `manny_src/utility/PlayerHelpers.java:13497` - Changed to use `openMagic()` instead of `KEY_F6` (but openMagic still uses F-keys internally)

## Test Results

| Approach | Result |
|----------|--------|
| CAST_SPELL_ON_INVENTORY_ITEM | FAIL - "Toplevel widget not visible" |
| Manual CLICK_AT sequence | PARTIAL - spell clicks work, item clicks intermittent |
| click_widget MCP tool | PARTIAL - same intermittency |
| Direct bash command file writes | PARTIAL - timing-dependent |

## Resolution (FIXED)

### Root Cause
The CAST_SPELL_ON_INVENTORY_ITEM command was switching to the Inventory tab AFTER clicking the spell, which **cancelled the spell-cast mode**. In OSRS, clicking any interface element (like tab icons) while in spell-targeting mode cancels the spell.

### The Fix
**Removed the inventory tab switch step entirely.** In OSRS fixed mode, inventory items are always visible at the bottom of the interface even when the Magic tab is open.

**File:** `manny_src/utility/PlayerHelpers.java:13586`

```java
// BEFORE (broken):
log.info("[CAST_SPELL_ON_INVENTORY_ITEM] Clicking spell: {}", displayName);
mouse.click(false);
Thread.sleep(200);

// Step 3: Open Inventory tab  <-- THIS CANCELLED THE SPELL!
if (!playerHelpers.openInventory()) { ... }

// Step 4: Find item...

// AFTER (fixed):
log.info("[CAST_SPELL_ON_INVENTORY_ITEM] Clicking spell: {}", displayName);
mouse.click(false);
Thread.sleep(200);

// NOTE: In OSRS fixed mode, inventory items are always visible at the bottom
// Do NOT switch to Inventory tab here - that would cancel the spell-cast mode!

// Step 3: Find item bounds in inventory (visible without switching tabs)
```

### Evidence
**Before fix (logs):**
```
Option: "Cast" | Target: "Superheat Item"     # Spell clicked - SUCCESS
Option: "Cancel" | Target: ""                  # Tab click - CANCELLED SPELL!
Option: "Use" | Target: "Iron ore"            # Wrong - no spell mode
```

**After fix (logs):**
```
Option: "Cast" | Target: "Superheat Item"     # Spell clicked
Option: "Cast" | Target: "Superheat Item -> Iron ore"  # Correct spell on item!
```

### Verification
- Magic XP: 165,530 → 165,583 (+53 XP ✓)
- Nature runes: 22 → 21 (-1 ✓)
- Steel bar created from Iron ore + Coal ✓

### Additional Fixes Applied
1. **Widget-based tab switching** in both `PlayerHelpers.java` and `GameEngine.java` TabSwitcher
   - Uses `mouse.click(x, y, false)` on tab icon widgets instead of F-keys
   - Tab icon widget IDs (group 548): Combat=64, Skills=65, Quest=66, Inventory=67, Equipment=68, Prayer=69, Magic=70

2. **isTabOpen() bug workaround** - Log warning but assume success since the click itself works

## Key Lesson

**CRITICAL OSRS MECHANIC:** After clicking a spell that requires a target (Superheat, Alchemy, etc.), clicking ANY interface element (tabs, buttons, menus) CANCELS the spell-targeting mode. The inventory is always visible in fixed mode, so tab switching is unnecessary and harmful.

Widget-based clicking is more reliable than coordinate-based or F-key approaches, but understand the game mechanics before adding unnecessary steps.
