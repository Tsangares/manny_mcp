## Smithing Context

**STATUS: VERIFIED** - Both smelting and anvil smithing workflows tested and working.

### Smelting Commands

```
SMELT_BAR <bar_type> [quantity]  - Click bar in smelting interface (requires interface open)
SMELT_BRONZE                     - Legacy command
SMELT_BRONZE_BARS <cycles>       - Smelt bronze with banking loop
```

**Note:** `SMELT_BAR` requires the smelting interface to already be open. Use `INTERACT_OBJECT Furnace Smelt` first.

### Smelting Workflow (VERIFIED)

```python
# 1. Travel to furnace (Al Kharid verified)
send_command("GOTO 3275 3186 0")

# 2. Interact with furnace - this opens interface AND starts smelting
send_command("INTERACT_OBJECT Furnace Smelt")

# The game auto-selects and smelts available ore!
# For specific bar types, use SMELT_BAR after interface opens
```

### Furnace Locations (VERIFIED)

| Location | Coordinates | Object ID | Notes |
|----------|-------------|-----------|-------|
| Al Kharid | 3272, 3186, 0 | 24009 | Close to bank |
| Lumbridge | TODO | TODO | Near castle |
| Falador | TODO | TODO | East side |
| Edgeville | TODO | TODO | Near bank |

### Ore Requirements

| Bar | Ores Required | Smithing Level | Notes |
|-----|--------------|----------------|-------|
| Bronze | 1 Tin + 1 Copper | 1 | 100% success |
| Iron | 1 Iron ore | 15 | **50% success** without ring |
| Steel | 1 Iron + 2 Coal | 30 | |
| Mithril | 1 Mithril + 4 Coal | 50 | |
| Adamant | 1 Adamant + 6 Coal | 70 | |
| Rune | 1 Runite + 8 Coal | 85 | |

### Full Smelting Loop Example

```python
# 1. Open bank
send_command("BANK_OPEN")

# 2. Withdraw ores
send_command("BANK_WITHDRAW Iron_ore 10")
# Note: Use underscore for "Iron_ore"

# 3. Close bank
send_command("BANK_CLOSE")

# 4. Go to furnace
send_and_await("GOTO 3275 3186 0", "location:3275,3186", timeout_ms=60000)

# 5. Smelt - auto-smelts all ore
send_command("INTERACT_OBJECT Furnace Smelt")
# Wait for smelting to complete
```

### Chat Messages

Smelting shows messages in chat (widget group 162):
- "You smelt the iron in the furnace." - Success
- (Various failure messages for iron without ring)

### Anvil Smithing (VERIFIED)

**Requirements:** Hammer + metal bars in inventory

```python
# 1. Travel to anvil (Varrock west verified)
send_command("GOTO 3188 3426 0")

# 2. Open smithing interface
send_command("INTERACT_OBJECT Anvil Smith")

# 3. Select item to smith (widget group 312)
find_and_click_widget(text="Bronze dagger", action="Smith")
# Or use click_text("Bronze dagger")
```

**Note:** `USE_ITEM_ON_OBJECT Bronze_bar Anvil` also works to open interface.

### Smithing Interface Widget IDs (Group 312)

Items appear with "Smith" action. Click to craft.

### Anvil Locations (F2P)

| Location | Coordinates | Object ID | Notes |
|----------|-------------|-----------|-------|
| Varrock West | 3188, 3426, 0 | 2097 | Near general store (VERIFIED) |
| Lumbridge | TODO | TODO | Near furnace |
| Falador | TODO | TODO | Multiple anvils |

### Known Issues

1. **SMELT_BAR fails if interface not open** - Returns "widget not found"
   - Workaround: Use `INTERACT_OBJECT Furnace Smelt` which auto-smelts

2. **Iron 50% success rate** - Without ring of forging, half the ore is lost

### TODO

- ~~Test anvil smithing workflow~~ DONE
- ~~Document anvil widget IDs~~ DONE (Group 312)
- ~~Test smithing interface item selection~~ DONE
- Test SMELT_BRONZE_BARS loop command
- Document more anvil/furnace locations
