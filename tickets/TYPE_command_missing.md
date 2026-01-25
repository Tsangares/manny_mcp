# Missing TYPE Command for Text Input

**Status:** RESOLVED (Not Needed)
**Severity:** High (blocks GE Buy automation)
**Created:** 2026-01-23
**Resolved:** 2026-01-24

## Problem

The plugin has no command to type text into search/input dialogs. This prevents:
- GE item searches (Buy offer requires typing item name)
- Entering custom quantities
- Entering custom prices
- Any chatbox-style text input

## Resolution

A standalone `TYPE` command was **not needed**. The GE commands handle text input internally:

- `GE_BUY <item> <quantity> [price%]` - Types item name into search automatically
- `GE_SEARCH <item>` - Atomic command for just the search step
- `GE_INPUT_QUANTITY <amount>` - Types custom quantity
- `GE_INPUT_PRICE <amount>` - Types custom price

### How GE_BUY Types Text

The `GEBuyCommand.java` method `typeSearchText()` handles typing:
1. Waits for search input widget to appear
2. Types each character with small delays
3. Waits for search results to populate

This internal approach is more reliable than a generic TYPE command because:
- It waits for the correct widget state before typing
- It handles the specific GE search workflow
- No race conditions between finding input field and typing

## Verification

Tested `GE_BUY Feather 100 5`:
- Search text "Feather" typed correctly
- Search results appeared
- Correct item selected from results
- Purchase completed successfully

## Related Documentation

- `discord_bot/context_fragments/grand_exchange.md` - Documents all GE commands
- `journals/ge_buy_smart_click_lessons_2026-01-24.md` - Lessons from GE debugging

## Related Files

- `/home/wil/Desktop/manny/utility/commands/GEBuyCommand.java`
