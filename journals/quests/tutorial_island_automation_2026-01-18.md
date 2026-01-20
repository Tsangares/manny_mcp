# Tutorial Island Automation - Session Journal
**Date:** 2026-01-18

## Directive

**Primary Goal:** Complete Tutorial Island automation on the `aux` account (LOSTimposter) while writing YAML routines for each section. Document all widget IDs, commands, and pitfalls discovered.

**User's exact words:** "finish the original directive. Like finish tutorial island completely while writing your yaml routines"

## Current Progress

### Completed Sections (Validated YAML)
| Section | YAML File | Status |
|---------|-----------|--------|
| 1. Character Creation | `01_character_creation.yaml` | DONE |
| 2. Gielinor Guide | `02_gielinor_guide.yaml` | DONE |
| 3. Survival Expert | `03_survival_expert.yaml` | DONE |
| 4. Fishing | `04_fishing.yaml` | DONE |
| 5. Cooking | `05_cooking.yaml` | DONE |
| 6. Quest Guide | `06_quest_guide.yaml` | DONE |
| 7. Mining/Smithing | `07_mining_smithing.yaml` | **IN PROGRESS - BLOCKED** |
| 8. Combat | `08_combat.yaml` | STUB |
| 9. Banking | `09_banking.yaml` | STUB |
| 10. Prayer/Magic | Not created | TODO |

### Current State
- **Account:** aux (LOSTimposter)
- **Location:** (3074, 9500, plane 0) - Underground mining area
- **Inventory:** 8 items including Bronze pickaxe
- **Tutorial Phase:** Mining - need to mine tin ore, then copper ore
- **Hint:** "Click a tin rock to mine tin ore. Then, click a copper rock to mine copper ore."

## Major Bug Discovered: Menu Index Inversion

### The Problem
`INTERACT_OBJECT Tin_rocks Mine` consistently clicks "Examine" instead of "Mine" on right-click menus.

### Root Cause
The menu array is ordered bottom-to-top, but the click Y-coordinate calculation treats it as top-to-bottom.

**Menu Array:**
```
[0] Cancel      <- Bottom of rendered menu
[1] Examine     <- System clicks HERE (targetIndex=1)
[2] Walk here
[3] Mine        <- System SHOULD click here (top of menu)
```

**Key Log Evidence:**
```
[MENU-DEBUG]   [0] Option='Cancel'
[MENU-DEBUG]   [1] Option='Examine' | StrippedTarget='Tin rocks'
[MENU-DEBUG]   [2] Option='Walk here'
[MENU-DEBUG]   [3] Option='Mine' | StrippedTarget='Tin rocks'
[MENU-DEBUG] Found option 'Mine' at targetIndex=1  <-- WRONG! Mine is at [3]

[MENU-VERIFY] Expected: 'Mine', Actual: 'Examine'  <-- Clicked wrong one
```

### Ticket Created
`/tmp/ticket_interact_object_menu_mismatch.md` - Full analysis with logs
`/tmp/interact_object_menu_bug_logs.txt` - Raw log dump

### Status
User indicated they fixed it and asked me to retry. After client restart, the fix may not have been applied, or there's another issue - clicks now land on empty ground ("Walk here" only in menu, no "Mine" or "Examine").

## Key Technical Discoveries

### 1. Tutorial Island Widget IDs (Different from Main Game!)

| Widget | ID | Group | Notes |
|--------|-----|-------|-------|
| Skills tab | 10485808 | 160 | NOT 35913809 (group 548) |
| Quest tab | 35913794 | 548 | `CLICK_WIDGET 35913794 "Quest List"` |
| Inventory | 35913795 | 548 | Standard |
| Continue button | 12648448 | 193 | Dialogue continue |

**Lesson:** Tutorial Island uses different widget groups than the main game. Always use `find_widget()` or `scan_widgets()` to discover IDs during validation.

### 2. Object Naming Conventions

| Scan Result | Menu Target | Notes |
|-------------|-------------|-------|
| "Tin" | "Tin rocks" | scan_tile_objects returns short name |
| "tin" | "Tin rocks" | Case varies |

The InteractionSystem finds objects by scan name but menu shows different target name with color tags: `<col=ffff>Tin rocks`

### 3. Useful Commands Validated

```python
# Dialogue - spam space for continue
send_input(input_type="key", key="space")

# Or use the tool
find_and_click_widget(text="Continue")

# Tab switching on Tutorial Island
send_command('CLICK_WIDGET 35913794 "Quest List"')  # Quest tab
send_command('CLICK_WIDGET 10485808')  # Skills tab (Tutorial Island specific)

# Walk to coordinates
send_command("GOTO 3080 9504 0")

# Interact with NPC
send_command("INTERACT_NPC Mining_Instructor Talk-to")
```

### 4. Playtime Management
- Accounts have 12hr/24hr playtime limits tracked in `~/.manny/sessions.yaml`
- User overrode the limit for this session
- To clear playtime: edit sessions.yaml, set `aux: []` under playtime, then `/mcp` to reconnect

## YAML Files Created/Updated This Session

### `routines/tutorial_island/06_quest_guide.yaml` - VALIDATED
```yaml
# Key Widgets - VALIDATED
widgets:
  continue_button: 12648448
  quest_tab: 35913794  # CLICK_WIDGET 35913794 "Quest List"

# VALIDATED COMMANDS:
# - GOTO 3086 3110 0
# - INTERACT_OBJECT Door Open
# - INTERACT_NPC Quest_Guide Talk-to
# - CLICK_WIDGET 35913794 "Quest List"
# - INTERACT_OBJECT Ladder Climb-down
```

### `routines/tutorial_island/07_mining_smithing.yaml` - PARTIAL
```yaml
npcs:
  mining_instructor:
    name: "Mining Instructor"
    id: 3311
    location: {x: 3080, y: 9502, plane: 0}

# VALIDATED SO FAR:
# - GOTO 3080 9504 0
# - INTERACT_NPC Mining_Instructor Talk-to
# - find_and_click_widget(text="Continue")

# BLOCKED AT:
# - Mining tin ore - INTERACT_OBJECT bug
```

### `routines/tutorial_island/03_survival_expert.yaml` - Updated
```yaml
widgets:
  skills_tab: 10485808  # Tutorial Island specific! (group 160)
```

### `routines/tutorial_island/05_cooking.yaml` - Updated
```yaml
# Correct exit door coordinates
exit_door: {x: 3072, y: 3090}
```

## Anti-Patterns Discovered

1. **Don't assume widget IDs from main game** - Tutorial Island has different groups
2. **Don't use INTERACT_OBJECT when menu index bug is present** - Use direct clicking as workaround
3. **Don't ignore "Examine" results** - Means you clicked a depleted rock or wrong target
4. **Don't trust scan_tile_objects name to match menu target** - "Tin" vs "Tin rocks"

## Debugging Commands That Helped

| Command | Purpose |
|---------|---------|
| `get_logs(level="ALL", since_seconds=30, grep="INTERACT")` | See exact menu entries and click positions |
| `scan_tile_objects("Tin")` | Find object names and locations |
| `get_screenshot()` | Visual confirmation of game state |
| `find_widget(text="Continue")` | Lightweight widget search |
| `get_game_state(fields=["dialogue"])` | Check dialogue.hint for next action |

## Interface Gaps Identified

- [x] **Menu index calculation bug** - User said they fixed it
- [ ] **Object name mismatch** - scan returns "Tin" but menu shows "Tin rocks"
- [ ] **Need MINE_ORE command** - Higher-level command that handles rock selection
- [ ] **Tutorial Island widget documentation** - Should be in CLAUDE.md

## Resume Instructions

1. **Check client status:**
   ```python
   check_health(account_id="aux")
   ```

2. **If not running, start:**
   ```python
   start_runelite(account_id="aux")
   # Wait ~60 seconds for full load
   ```

3. **Verify location:**
   ```python
   get_game_state(fields=["location", "inventory"])
   # Should be at ~(3074, 9500, plane 0) with Bronze pickaxe
   ```

4. **Test the menu fix:**
   ```python
   send_and_await(
       command="INTERACT_OBJECT Tin_rocks Mine",
       await_condition="has_item:Tin ore",
       timeout_ms=15000
   )
   ```

5. **If still failing, check logs:**
   ```python
   get_logs(level="ALL", since_seconds=30, grep="INTERACT")
   ```

6. **After mining tin, continue with:**
   - Mine copper ore
   - Smelt bronze bar at furnace
   - Smith bronze dagger at anvil
   - Continue to combat section

## Files to Reference

| File | Contents |
|------|----------|
| `/tmp/ticket_interact_object_menu_mismatch.md` | Full bug analysis |
| `/tmp/interact_object_menu_bug_logs.txt` | Raw logs showing the bug |
| `routines/tutorial_island/*.yaml` | All Tutorial Island routines |
| `~/.manny/sessions.yaml` | Playtime tracking |

## Session Summary

Started with aim to complete Tutorial Island. Made it through Quest Guide section (parts 1-6) with validated YAML. Got stuck in Mining section due to menu index inversion bug in INTERACT_OBJECT. User fixed the bug but after client restart, still having issues with clicks landing on empty ground. Session ended here - resume by testing the fix and continuing mining tutorial.
