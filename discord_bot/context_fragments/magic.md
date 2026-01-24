## Magic Context

### Spellcasting Commands

```
CAST_SPELL_NPC <spell> <npc>              - Cast combat spell on NPC
CLICK_NPC <npc>                           - Click NPC (after selecting spell)
CAST_SPELL_ON_GROUND_ITEM <spell> <item>  - Telegrab etc.
TELEGRAB_WINE_LOOP                        - Automated wine of zamorak telegrab
```

### Combat Spells

**Casting on NPCs:**
```python
send_command("CAST_SPELL_NPC Wind_Strike Chicken")
send_command("CAST_SPELL_NPC Fire_Strike Cow")
```

**Spell names use underscores:** `Wind_Strike`, `Fire_Strike`, `Earth_Bolt`

### Teleportation

**Home Teleport (no runes required):**
```python
# Use the MCP tool for home teleport
teleport_home()  # Opens magic tab, clicks spell, waits for arrival
```

**Standard teleports require runes:**
| Teleport | Level | Runes |
|----------|-------|-------|
| Lumbridge Home | 0 | None (30 min cooldown) |
| Varrock | 25 | 1 Law, 3 Air, 1 Fire |
| Lumbridge | 31 | 1 Law, 3 Air, 1 Earth |
| Falador | 37 | 1 Law, 3 Air, 1 Water |

### Telegrab

**For items you can't reach (wine of zamorak, etc.):**
```python
send_command("CAST_SPELL_ON_GROUND_ITEM Telekinetic_Grab Wine_of_zamorak")
```

**Automated loop:**
```python
send_command("TELEGRAB_WINE_LOOP")  # Continuous wine grabbing
```

### Magic Tab

```
TAB_OPEN magic           - Open magic spellbook tab
```

### Discovery Pattern

1. **Check magic level:** `get_game_state(fields=["skills"])`
2. **Check runes:** `get_game_state(fields=["inventory"])`
3. **Cast spell:** `CAST_SPELL_NPC <spell> <target>`

### Common Issues

- **"No runes"** → Check inventory for required runes
- **"Level too low"** → Check magic level requirement
- **Spell not working** → Ensure target is valid (NPC exists, in range)

### Spell Naming

Use underscores for multi-word spells:
- `Wind_Strike`, `Water_Strike`, `Earth_Strike`, `Fire_Strike`
- `Wind_Bolt`, `Water_Bolt`, `Earth_Bolt`, `Fire_Bolt`
- `Telekinetic_Grab`
- `Bones_to_Bananas`
