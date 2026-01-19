# Tutorial Island Automation - Lessons Learned
**Date:** 2026-01-18

## The Problem

Tutorial Island automation revealed multiple interface gaps and broken commands that required manual intervention. The biggest blockers were: spell casting on NPCs (CAST_SPELL_NPC broken), dialogue advancement issues, and inventory widget bounds returning wrong positions.

## Root Cause

Multiple issues stem from:
1. **CAST_SPELL_NPC**: Command exists but causes client-breaking behavior
2. **Dialogue handling**: KEY_PRESS space doesn't consistently advance dialogue on Tutorial Island
3. **Widget bounds**: Inventory grid calculation was wrong; equipment stats panel uses dynamic widgets with -1,-1 bounds

## Key Lessons

### 1. CAST_SPELL_NPC is Broken

**What happened:** Attempting to cast Wind Strike on a chicken via `CAST_SPELL_NPC Wind_Strike Chicken` caused client issues and required manual intervention.

**Why:** Unknown - needs investigation in `PlayerHelpers.java`

**Solution:**
```python
# BAD - causes client issues
send_command("CAST_SPELL_NPC Wind_Strike Chicken")

# WORKAROUND - manual intervention required
# 1. Click Wind Strike spell in magic tab
# 2. Click on chicken
# Status: NEEDS FIX in plugin
```

### 2. click_text() > KEY_PRESS space for Dialogue

**What happened:** KEY_PRESS space failed to advance dialogue reliably. The hint said "CLICK_CONTINUE" but the actual clickable text was "Click here to continue".

**Why:** Tutorial Island may have different dialogue widgets, or timing issues with KEY_PRESS.

**Solution:**
```python
# BAD - unreliable on Tutorial Island
send_command("KEY_PRESS space")
send_command("KEY_PRESS space")  # repeat hoping it works

# GOOD - directly clicks the text
click_text("continue")  # Partial match works
click_text("Click here to continue")  # Full text also works
```

### 3. Ironman Dialogue is Confusing

**What happened:** The Ironman question has a two-step flow that looks backwards:
1. First prompt asks if ready to leave - click "Yes"
2. Second prompt asks about Ironman mode - click "No"

**Why:** The dialogue flow is: "Yes" = continue conversation, "No" = decline Ironman mode. They're different questions.

**Solution:**
```python
# Correct sequence:
click_text("Yes")   # Continue with tutorial
click_text("No")    # Decline Ironman mode
click_text("continue")  # Multiple times until teleport
```

### 4. Tutorial Island Widget IDs are Different

**What happened:** Main game tab widget IDs don't work on Tutorial Island. Had to discover Tutorial Island-specific IDs.

**Why:** Tutorial Island uses a restricted interface with different widget groups.

**Key Widget IDs (Tutorial Island):**
| Tab | Widget ID |
|-----|-----------|
| Account Management | 35913777 |
| Prayer | 35913797 |
| Magic | 35913798 |
| Equipment (Worn) | 35913771 |
| Combat Options | 35913792 |

### 5. Door Navigation Pattern

**What happened:** Clicking doors from a distance often failed. Needed to walk to the door first.

**Why:** INTERACT_OBJECT has limited range and pathfinding through closed doors fails.

**Solution:**
```python
# BAD - may fail if too far
send_command("INTERACT_OBJECT Door Open")

# GOOD - walk to door, then open
send_command("GOTO 3124 3124 0")  # Position in front of door
# Wait for arrival
send_command("INTERACT_OBJECT Door Open")
```

### 6. Equipment Stats Panel Has Dynamic Widgets

**What happened:** Opening the equipment stats panel made inventory items unclickable - bounds returned -1,-1.

**Why:** The equipment stats panel uses dynamic/virtual widgets that don't have proper bounds.

**Solution:**
```python
# BAD - trying to click items while stats panel is open
equip_item("Bronze dagger")  # Fails - bounds are -1,-1

# GOOD - close panel first
send_command("KEY_PRESS Escape")  # Close equipment stats panel
equip_item("Bronze dagger")  # Now works
```

## Anti-Patterns

1. **Don't** use KEY_PRESS space repeatedly for dialogue - use click_text("continue")
2. **Don't** assume CAST_SPELL_NPC works - it's broken, needs manual intervention
3. **Don't** click doors from far away - walk to position first
4. **Don't** use coordinate clicking (send_input click x y) - causes server disconnections
5. **Don't** open equipment stats panel before clicking inventory items

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_dialogue()` | See dialogue type, hint, and options |
| `get_game_state(fields=["location", "dialogue"])` | Check position and dialogue state efficiently |
| `find_widget(text="X")` | Discover widget IDs by text/action |
| `query_nearby()` | See what NPCs and objects are around |
| `click_text("X")` | Click dialogue options or UI text |

## Interface Gaps Identified

- [x] Plugin needs: Fix CAST_SPELL_NPC command
- [x] Plugin needs: Better dialogue handling (space key consistency)
- [x] MCP needs: Documentation about Tutorial Island widget differences
- [x] CLAUDE.md needs: Add Tutorial Island specific patterns

## Files Modified

| File | Change |
|------|--------|
| `routines/tutorial_island/10_prayer_magic.yaml` | Complete magic section documentation |
| `routines/tutorial_island/08_combat.yaml` | Equipment/combat patterns |
| `routines/tutorial_island/09_banking.yaml` | Banking section patterns |
| `routines/tutorial_island/widget_reference.yaml` | Widget ID reference |

## Working Patterns Summary

### Dialogue Handling
```python
# Check dialogue state
dialogue = get_dialogue()
if dialogue["has_continue"]:
    click_text("continue")
elif dialogue["options"]:
    click_text("Yes")  # or specific option
```

### Tab Opening
```python
# Use MCP tools for tabs
click_widget(widget_id=35913797)  # Prayer tab
# OR
find_and_click_widget(text="Worn Equipment")  # Equipment tab
```

### Item Equipping
```python
# After closing any overlay panels
equip_item(item_name="Bronze sword")
```

### NPC Interaction
```python
send_command("INTERACT_NPC Magic_Instructor Talk-to")
# Wait for dialogue
dialogue = get_dialogue()
```

## Time Lost to Issues

| Issue | Time Lost | Status |
|-------|-----------|--------|
| CAST_SPELL_NPC broken | ~30 min | NEEDS FIX |
| Dialogue space key issues | ~20 min | WORKAROUND: click_text |
| Equipment stats panel bounds | ~15 min | FIXED in code |
| Ironman dialogue confusion | ~10 min | DOCUMENTED |

## Recommendations for Future Tutorial Island Runs

1. Always use `click_text("continue")` for dialogue
2. Skip CAST_SPELL_NPC - do spell casting manually
3. Use validated widget IDs from widget_reference.yaml
4. Close equipment stats panel before clicking inventory
5. Walk to doors before opening them
