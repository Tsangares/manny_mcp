# Quest NPC Dialogue Navigation - Lessons Learned
**Date:** 2026-01-27

## The Problem

During Romeo & Juliet quest, needed to get a Cadava potion from the Apothecary. `USE_ITEM_ON_NPC Cadava_berries Apothecary` executed successfully but didn't trigger the expected quest dialogue or item exchange.

## Root Cause

Quest NPCs with multiple functions (shop + quest) require navigating through dialogue options to access quest-specific content. The Apothecary's default interaction opens a potion shop interface, not the quest dialogue. Using items on the NPC doesn't bypass this - you must talk and select specific dialogue branches.

## Key Lessons

### 1. Quest NPCs Require Dialogue Tree Navigation

**What happened:** USE_ITEM_ON_NPC succeeded per logs but no quest dialogue appeared.
**Why:** The Apothecary has multiple roles - potion shop (default) and quest helper. Quest content is behind dialogue options, not item-use triggers.
**Solution:**
```python
# BAD - assumes item use triggers quest dialogue
send_command("USE_ITEM_ON_NPC Cadava_berries Apothecary")
# Nothing happens - NPC doesn't recognize quest context from item

# GOOD - navigate dialogue tree to quest-specific branch
send_command("INTERACT_NPC Apothecary Talk-to")
click_continue()  # "I am the Apothecary. I brew potions..."
click_text("Talk about something else")  # Key branch!
click_text("Talk about Romeo & Juliet")  # Quest dialogue
# Now NPC recognizes quest context and accepts berries
```

### 2. Dialogue Options Work Reliably with click_text()

**What happened:** Earlier session had issues clicking dialogue options, but `click_text()` worked consistently.
**Why:** The tool searches visible widgets by text content and clicks the matching one.
**Solution:**
```python
# Works for dialogue options
click_text("Talk about something else")
click_text("Talk about Romeo & Juliet")

# For "Click here to continue" - use click_continue() or Space key
click_continue()
# OR
send_input(input_type="key", key="Space")
```

### 3. Multi-word Item Names Need Underscores in Commands

**What happened:** `USE_ITEM_ON_NPC Cadava berries Apothecary` failed - NPC not found.
**Why:** Parser splits on spaces. "Cadava berries" becomes item="Cadava", NPC="berries Apothecary".
**Solution:**
```python
# BAD - spaces cause parsing error
send_command("USE_ITEM_ON_NPC Cadava berries Apothecary")
# Logs show: [USE_ITEM_ON_NPC] NPC not found: berries Apothecary

# GOOD - underscores for multi-word items
send_command("USE_ITEM_ON_NPC Cadava_berries Apothecary")
```

## Anti-Patterns

1. **Don't** assume USE_ITEM_ON_NPC triggers quest dialogue - many quest NPCs require explicit dialogue navigation
2. **Don't** use spaces in multi-word item names for commands - always use underscores
3. **Don't** skip dialogue options looking for shortcuts - quest content is often hidden in "Talk about something else" branches

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_dialogue()` | Check if dialogue is open and see available options |
| `get_screenshot()` | Visual confirmation of dialogue state |
| `get_logs(grep="USE_ITEM")` | Verify command parsing was correct |

## Interface Gaps Identified

- [ ] CLAUDE.md needs: Document common quest NPC dialogue patterns
- [ ] Consider: Auto-detect quest-related dialogue options in get_dialogue() response

## Quest-Specific Note: Romeo & Juliet

Apothecary dialogue path for Cadava potion:
1. Talk-to Apothecary
2. "Talk about something else"
3. "Talk about Romeo & Juliet"
4. Click through dialogue - game auto-detects Cadava berries in inventory
5. Receive Cadava potion
