# GE Commands Development Plan

**Date:** 2026-01-18
**Status:** Commands created, testing incomplete

## Commands Created

### 1. GE_ABORT
**File:** `manny_src/utility/commands/GEAbortCommand.java`
**Usage:** `GE_ABORT [slot]`
- Aborts pending GE offers
- If slot specified (1-8), aborts that slot
- If no slot, finds first active offer and aborts it
- Works via "Abort offer" widget action or right-click menu

### 2. GE_COLLECT
**File:** `manny_src/utility/commands/GECollectCommand.java`
**Usage:** `GE_COLLECT [inventory|bank]`
- Collects items/coins from completed offers
- Default: `inventory`
- `GE_COLLECT bank` - collects to bank
- Uses widget actions "Collect to inventory" / "Collect to bank"

### 3. GE_BUY (Fast Buy)
**File:** `manny_src/utility/commands/GEBuyCommand.java`
**Usage:** `GE_BUY <item_name> <quantity> [price_percent]`
- High-level command for quick buying
- Starts at +10% above guide price (or specified percent)
- Waits 5 seconds, if not filled increases by +10%
- Max 3 retry attempts
- Auto-collects when complete
- Example: `GE_BUY Air_rune 100 20` (start at +20%)

### 4. GE_SLOW_BUY (Patient Buy)
**File:** `manny_src/utility/commands/GESlowBuyCommand.java`
**Usage:** `GE_SLOW_BUY <item_name> <quantity> [max_wait_minutes]`
- Patient buying at guide price (no markup)
- Default wait: 5 minutes
- Checks every 30 seconds
- Returns success even for partial fills
- Ideal for bulk buying when time isn't critical
- Example: `GE_SLOW_BUY Lobster 1000 10` (wait up to 10 min)

## Existing GE Commands (for reference)
- `GE_CLICK_BUY [slot]` - Click buy button on slot
- `GE_CLICK_SELL [slot]` - Click sell button on slot
- `GE_SELL_ITEM <item_name>` - Select inventory item for selling
- `GE_SEARCH <item_name>` - Type in search box
- `GE_SELECT_ITEM <item_name>` - Click item in search results
- `GE_CANCEL` - Press Escape to close

## Registration in PlayerHelpers.java
All commands registered at:
- Field declarations: ~line 9518-9525
- Instantiations: ~line 9704-9712
- Switch cases: ~line 10103-10119

## Known Issues / Bugs Discovered

### 1. Menu Position Calculation Bug (CRITICAL)
When the GE is crowded, INTERACT_NPC produces invalid menu coordinates:
```
[MENU-RETRY] Recalculated position: (220, -967) for index 97
```
Negative Y coordinates cause clicks to miss the menu entirely.

**Root cause:** Too many players create a menu with 95+ entries, and the position calculation overflows or miscalculates.

**Workaround:** Use less crowded worlds, or use direct widget clicking instead of NPC interaction.

### 2. GE_BUY/GE_SLOW_BUY Helper Methods Incomplete
The following methods are stubbed out and need implementation:
- `clickQuantityButton(String button)` - needs to find +1/+10/+100/+1k buttons
- `clickPriceButton(String button)` - needs to find +5%/-5% buttons
- `abortOffer(int slot)` - needs to call GE_ABORT logic
- `collectItems()` - needs to call GE_COLLECT logic

**Fix:** Either:
1. Implement the widget finding logic in these methods
2. Or refactor to call the existing lower-level commands

### 3. GE Interface Widget IDs
From previous testing:
- GE Interface Group: 465
- Collect button container: child 6
- Offer status/abort: child 23
- Slot offset: slots 1-8 map to children 7-14

## Testing TODO

### Basic Tests
- [ ] GE_COLLECT inventory - collect items to inventory
- [ ] GE_COLLECT bank - collect items to bank
- [ ] GE_ABORT - abort an active offer
- [ ] GE_ABORT 1 - abort specific slot

### Integration Tests
- [ ] GE_BUY Air_rune 10 - buy 10 air runes
- [ ] GE_SLOW_BUY Lobster 100 2 - buy 100 lobsters, wait 2 min
- [ ] Full workflow: open GE → buy item → collect

### Edge Cases
- [ ] GE_COLLECT when nothing to collect
- [ ] GE_ABORT when no active offers
- [ ] GE_BUY with item not found
- [ ] GE_BUY when no empty slots

## Future Improvements

1. **GE_SELL command** - High-level sell equivalent to GE_BUY
2. **Price lookup** - Get guide price before buying
3. **Offer status check** - Query current offer states
4. **Better quantity input** - Direct typing instead of button clicking
5. **World hop on crowded GE** - Auto-hop if menu issues detected

## How to Test

```python
# 1. Make sure character is at GE
get_game_state(account_id="main", fields=["location"])

# 2. Open GE manually or via booth click
# (INTERACT_NPC is buggy in crowded areas)

# 3. Test individual commands
send_command("GE_CLICK_BUY 1", account_id="main")
send_command("GE_SEARCH Air rune", account_id="main")
send_command("GE_COLLECT", account_id="main")
send_command("GE_ABORT", account_id="main")

# 4. Check logs for errors
get_logs(account_id="main", level="ALL", since_seconds=30)
```

## Files Modified

| File | Changes |
|------|---------|
| `GEAbortCommand.java` | New file |
| `GECollectCommand.java` | New file |
| `GEBuyCommand.java` | New file |
| `GESlowBuyCommand.java` | New file |
| `PlayerHelpers.java` | Added imports, fields, instantiations, switch cases |
