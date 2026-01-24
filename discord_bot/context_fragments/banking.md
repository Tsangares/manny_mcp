## Banking Context

### Banking Workflow
```
1. BANK_OPEN           # Opens nearest bank booth/chest
2. BANK_DEPOSIT_ALL    # Deposits entire inventory
3. BANK_WITHDRAW <item> <qty>  # Withdraw items
4. BANK_CLOSE          # Close bank interface
```

### Commands
```
BANK_OPEN                     # Open bank (must be near banker/booth)
BANK_CLOSE                    # Close bank interface
BANK_DEPOSIT_ALL              # Deposit everything
BANK_DEPOSIT <item>           # Deposit specific item
BANK_WITHDRAW <item> <qty>    # Withdraw items (e.g., BANK_WITHDRAW Lobster 10)
```

### BANK vs DROP - Important Distinction!
- `BANK_DEPOSIT_ALL` = Items go to bank (SAVED)
- `DROP_ALL` = Items fall on ground (DESTROYED/LOST)

**Never use DROP when user means BANK!**

### Discovery Pattern
1. **Check location**: get_game_state(fields=["location"])
2. **Find bank**: lookup_location(location="<area> bank") or query_nearby(name_filter="Bank")
3. **Walk there**: GOTO if not nearby
4. **Execute**: BANK_OPEN -> BANK_DEPOSIT_ALL -> BANK_CLOSE

### Common Bank Locations
| Bank | Coordinates |
|------|-------------|
| Draynor | 3093, 3244 |
| Lumbridge (top floor) | 3208, 3220, 2 |
| Varrock West | 3253, 3420 |
| Grand Exchange | 3165, 3487 |
