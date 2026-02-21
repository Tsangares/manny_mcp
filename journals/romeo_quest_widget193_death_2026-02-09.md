# Romeo & Juliet Quest - Widget 193 and Dark Wizard Death
**Date:** 2026-02-09

## The Problem

Two critical failures during Romeo & Juliet quest on monkey (StonedMonkie) account:
1. Widget group 193 dialogues are invisible to all dialogue tools, causing quest dialogue loops and Death tutorial softlock
2. Player died to Dark Wizards while navigating to cadava bushes through the danger zone (~3230, 3375)

## Root Cause

### Widget 193 Not Handled by Dialogue System

Widget group 193 is a "special item/quest handover" interface used for:
- Quest item handovers ("You hand over Juliet's message to Romeo")
- Item folding animations ("Romeo folds the message away")
- Death's Domain tutorial dialogue pages

**The CLICK_CONTINUE command** (ClickContinueCommand.java) only searches groups `{192, 217, 219, 229, 231}` - **group 193 is missing**.

**The dialogue state detection** (GameEngine.java line ~6340-6372) checks groups 217, 219, 231 for dialogue - **group 193 is not checked**, so `get_game_state(fields=["dialogue"])` reports `"type": "none"` when widget 193 is the active dialogue.

**The RandomEventHandler** was also mapping group 193 to "Drill Demon", causing false positives on quest handovers (fixed earlier by commenting out case 193).

### Dark Wizard Death - Incorrect Pathfinding Route

The cadava berry return route went THROUGH the Dark Wizard stone circle at (~3224, 3370-3389). The GOTO command from (3230, 3375) to (3212, 3375) caused the pathfinder to route through wizard aggro range. With only bronze sword and 31 HP, the level-7 Dark Wizards killed the player.

The YAML routine had waypoints going east to avoid wizards on the way TO cadava bushes, but the MANUAL navigation I used going back west did NOT follow the safe east route.

## Key Lessons

### 1. Widget Group 193 is a Hidden Dialogue Interface

**What happened:** After clicking through Romeo's NPC dialogue (group 231), widget 193 appeared with "You hand over Juliet's message to Romeo." but was invisible to all dialogue tools.
**Why:** Group 193 is not in ClickContinueCommand's CONTINUE_GROUPS array, and not in GameEngine's dialogue detection.
**Solution:**
```java
// BAD - group 193 missing
private static final int[] CONTINUE_GROUPS = {192, 217, 219, 229, 231};

// GOOD - added group 193
private static final int[] CONTINUE_GROUPS = {192, 193, 217, 219, 229, 231};
```

### 2. Death Tutorial Requires Widget 193 Continue Between Each Page

**What happened:** Death's Domain tutorial showed one page on group 231, then the NEXT page appeared on group 193. Since widget 193 continue wasn't clicked properly, the tutorial reset to page 1 each time.
**Why:** The dialogue flow is: group 231 (Death speaks) -> group 193 (continue) -> close -> Talk again for next page. Missing the group 193 click meant the server never registered the page as "read".
**Solution:** Fix CLICK_CONTINUE to include group 193 (done).

### 3. Dark Wizards Kill Low-Level Accounts Quickly

**What happened:** Player at (3230, 3375) navigated west and the pathfinder routed through Dark Wizard aggro range. Died in seconds.
**Why:** Dark Wizards (level 7, aggressive) camp the stone circle at ~(3224, 3370). They cast magic which hits through low defence. At 31 HP with bronze sword, there's no escape.
**Solution:** YAML routine already has eastern waypoints. The death happened because I was navigating MANUALLY instead of following the routine's safe waypoints.

### 4. Always Use the YAML Routine, Never Navigate Manually

**What happened:** Instead of following the routine's eastern waypoint path (step 15a→15b→15c), I tried to walk directly west from cadava bushes through the danger zone.
**Why:** Manual pathfinding shortcuts through dangerous areas. The routine's waypoints were specifically designed to avoid Dark Wizards.
**Solution:** ALWAYS follow the YAML routine for navigation. Never "shortcut" through areas marked as dangerous.

## Anti-Patterns

1. **Don't navigate manually around Dark Wizards** - Use the YAML routine's validated waypoints every time
2. **Don't assume dialogue closed = dialogue done** - Widget 193 can appear as an invisible "hidden" dialogue page
3. **Don't click widget 193 with bounds** - Use `click_widget(id)` without bounds for proper WIDGET_CONTINUE action dispatch
4. **Don't retry Talk-to when dialogue "resets"** - Check ALL widget groups (193, 217, 219, 231) before concluding dialogue is done

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `scan_widgets(group=193)` | Check for hidden widget 193 dialogue |
| `scan_widgets(group=231, filter_text=".")` | Read NPC dialogue text to track progress |
| `get_game_state(fields=["dialogue"])` | NOTE: Does NOT detect group 193! |
| `click_widget(15138821)` | Click group 231 continue (no bounds) |
| `click_widget(12648448)` | Click group 193 continue (no bounds) |

## Interface Gaps Identified

- [x] Plugin needs: Add group 193 to ClickContinueCommand CONTINUE_GROUPS array (DONE)
- [x] Plugin needs: Fix nested child clicking in ClickContinueCommand - use clickWidgetDirect instead of clickWidget(id) (DONE)
- [x] MCP needs: Stuck detection to prevent bot-like command spam loops (DONE - mcptools/stuck_detector.py)
- [x] MCP needs: Fix playtime tracking to use active time, not wall-clock (DONE - session_manager.py)
- [ ] Plugin needs: Add group 193 to GameEngine dialogue state detection
- [ ] Plugin needs: RandomEventHandler should verify Drill Demon more specifically (not just widget 193 presence)
- [ ] MCP click_continue tool should call CLICK_CONTINUE command (which now handles 193) instead of its own implementation
- [ ] YAML routine needs: Add health check / eat food step before entering Dark Wizard zone
- [ ] YAML routine needs: Validate return route waypoints from cadava bushes

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/ClickContinueCommand.java` | Added group 193 to CONTINUE_GROUPS; uses clickWidgetDirect for nested children |
| `manny_src/utility/WidgetClickHelper.java` | Added clickWidgetDirect(Widget) method for clicking nested children by bounds |
| `manny_src/utility/PlayerHelpers.java` | Commented out case 193 "Drill Demon" in RandomEventHandler (previous session) |
| `mcptools/stuck_detector.py` | NEW - Detects repeated commands with no state change (warns at 3, blocks at 6) |
| `mcptools/tools/commands.py` | Integrated stuck detection into send_command and send_input |
| `mcptools/session_manager.py` | Fixed playtime to use state file freshness for active time; auto-cleanup orphaned sessions |
