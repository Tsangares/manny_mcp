## Smithing Context

### Smelting Commands

```
SMELT_BAR <bar_type>         - Smelt ore into bars
SMELT_BRONZE                 - Smelt bronze bars specifically
SMELT_BRONZE_BARS            - Alternative bronze smelting command
```

### Ore Requirements

| Bar | Ores Required | Smithing Level |
|-----|--------------|----------------|
| Bronze | 1 Tin + 1 Copper | 1 |
| Iron | 1 Iron ore | 15 (50% success without ring) |
| Steel | 1 Iron + 2 Coal | 30 |
| Mithril | 1 Mithril + 4 Coal | 50 |
| Adamant | 1 Adamant + 6 Coal | 70 |
| Rune | 1 Runite + 8 Coal | 85 |

### Furnace Locations (F2P)

| Location | Coordinates | Notes |
|----------|-------------|-------|
| Lumbridge | TODO | Near castle |
| Al Kharid | 3275, 3186, 0 | Close to bank |
| Falador | TODO | East side |
| Edgeville | TODO | Near bank |

### Smelting Workflow

```python
# 1. Get ores from bank
send_command("BANK_OPEN")
send_command("BANK_WITHDRAW Tin_ore 14")
send_command("BANK_WITHDRAW Copper_ore 14")
send_command("BANK_CLOSE")

# 2. Go to furnace
send_command("GOTO 3275 3186 0")  # Al Kharid

# 3. Smelt
send_command("SMELT_BRONZE")
# or
send_command("INTERACT_OBJECT Furnace Smelt")
```

### Smithing at Anvil

```
USE_ITEM_ON_OBJECT <bar> Anvil    - Use bar on anvil to smith
```

**TODO:** Need commands for:
- Selecting what to smith (interface)
- Smithing multiple items
- Anvil locations

### Mining → Smelting → Smithing Loop

```python
# 1. Mine ores
send_command("MINE_ORE")  # or POWER_MINE

# 2. Bank ores
send_command("BANK_DEPOSIT_ALL")

# 3. Withdraw and smelt
send_command("BANK_WITHDRAW Tin_ore 14")
send_command("BANK_WITHDRAW Copper_ore 14")
send_command("SMELT_BRONZE")

# 4. Smith items
send_command("USE_ITEM_ON_OBJECT Bronze_bar Anvil")
```

### Ore Locations (F2P)

| Ore | Location | Notes |
|-----|----------|-------|
| Copper/Tin | Lumbridge Swamp | Near mining tutor |
| Iron | Al Kharid | Multiple rocks |
| Coal | Mining Guild | Requires 60 Mining |

**TODO:** Need more detail on:
- Exact furnace coordinates
- Anvil locations
- Smithing interface widget IDs
