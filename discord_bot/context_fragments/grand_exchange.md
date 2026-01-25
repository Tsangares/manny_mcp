## Grand Exchange Context

**STATUS: VERIFIED** - GE_BUY and GE_SELL tested and working (2026-01-24).

### GE Location

| Location | Coordinates |
|----------|-------------|
| Grand Exchange | 3165, 3487, 0 |

### High-Level Commands (RECOMMENDED)

```python
# Buy items - handles full workflow automatically
send_command("GE_BUY Feather 100 5")       # Buy 100 feathers at +5% price
send_command("GE_BUY Air_rune 500 10")     # Buy 500 air runes at +10%
send_command("GE_BUY Lobster 100")         # Buy 100 lobsters (default +10%)

# Sell items - handles full workflow automatically
send_command("GE_SELL Cowhide 50 -10")     # Sell 50 cowhides at -10%
send_command("GE_SELL Raw_lobster")        # Sell ALL raw lobsters at default price
```

**Command Format:**
- `GE_BUY <item> <quantity> [price_percent]` - Buy items (price_percent default: +10%)
- `GE_SELL <item> [quantity] [price_percent]` - Sell items (quantity default: ALL)

### What GE_BUY Does Automatically

1. Opens GE if not open (interacts with clerk)
2. Finds an empty slot
3. Clicks Buy button
4. Types item name in search
5. Selects item from results
6. Sets quantity (+1, +10, +100 buttons)
7. Sets price (+5%, +10% buttons)
8. Confirms offer
9. Waits for completion
10. Collects items to inventory

### Atomic Commands (For Manual Control)

```python
# Open GE interface
send_command("GE_OPEN")

# Search for item (types into search box)
send_command("GE_SEARCH Feather")

# Click slot buttons (slot 1-8)
send_command("GE_CLICK_BUY 1")
send_command("GE_CLICK_SELL 1")

# Quantity adjustment
send_command("GE_SET_QUANTITY +1")
send_command("GE_SET_QUANTITY +10")
send_command("GE_SET_QUANTITY +100")
send_command("GE_SET_QUANTITY All")
send_command("GE_INPUT_QUANTITY 500")     # Type exact quantity

# Price adjustment
send_command("GE_ADJUST_PRICE +5%")
send_command("GE_ADJUST_PRICE +10%")
send_command("GE_ADJUST_PRICE -5%")
send_command("GE_INPUT_PRICE 150")        # Type exact price

# Finalize
send_command("GE_CONFIRM")                # Confirm offer
send_command("GE_COLLECT")                # Collect to inventory
send_command("GE_ABORT")                  # Abort current offer
send_command("GE_CANCEL")                 # Cancel/back out
```

### Widget IDs Reference (Group 465)

| Widget | ID | Purpose |
|--------|----|---------|
| Container | 30474240 | Main GE window |
| Slot 1 | 30474247 | First slot (Buy/Sell buttons) |
| Slot 2 | 30474248 | Second slot |
| Slots 3-8 | 30474249-54 | Remaining slots |
| Confirm | 30474270 | Confirm offer button |
| Collect | 30474246 | Collect button |

### Item Name Rules

**Use underscores for multi-word items:**
```python
# CORRECT
send_command("GE_BUY Air_rune 100")
send_command("GE_BUY Cooked_lobster 50")

# WRONG - spaces cause parsing errors
send_command("GE_BUY Air rune 100")  # Fails!
```

### GE Tips

- GE has 8 slots total (3 for F2P accounts)
- GE_BUY/GE_SELL automatically find empty slots
- Price percent: positive = faster buy, negative = faster sell
- Items are auto-collected after successful trades
- Must be at GE location (near clerk) to use commands

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Unexpected offer state" | GE wasn't on slots overview - command handles this now |
| Search not working | Verify GE interface is open first |
| Only bought 1 item | Fixed in 2026-01-24 update (smart click) |
| Clicks not registering | Plugin uses smart click pattern now |

### Common GE Items

| Category | Items |
|----------|-------|
| Food | Lobster, Swordfish, Shark, Cooked_lobster |
| Runes | Law_rune, Nature_rune, Air_rune, Fire_rune |
| Potions | Strength_potion, Prayer_potion |
| Materials | Cowhide, Clay, Iron_ore, Feather |
| Combat | Bronze_arrow, Iron_scimitar |

### Full Workflow Example

```python
# Navigate to GE
send_command("GOTO 3165 3487 0")

# Buy 100 feathers at +5% (all steps automated)
send_command("GE_BUY Feather 100 5")

# Sell all cowhides at -10% for quick sale
send_command("GE_SELL Cowhide -10")
```
