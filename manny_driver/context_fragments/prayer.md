## Prayer Context

### Burying Bones

```
BURY_ALL                - Bury all bones in inventory
BURY_ITEM <bone_type>   - Bury specific bone type
```

### Bone Types and XP

| Bone | XP | Common Source |
|------|-----|---------------|
| Bones | 4.5 | Chickens, goblins, most monsters |
| Big bones | 15 | Giants, ogres, moss giants |
| Dragon bones | 72 | Dragons (members) |

### Combat + Bury Pattern

```python
# Kill monsters, collect bones, bury when full
send_command("KILL_LOOP Giant_frog none 100")
# After combat...
send_command("BURY_ALL")
```

### Bone Collection in KILL_LOOP

KILL_LOOP can auto-loot bones. Check combat.md for loot configuration.

### Prayer Training Locations

| Method | Location | Notes |
|--------|----------|-------|
| Chickens | Lumbridge | Easy bones, low XP |
| Cows | Lumbridge | Bones + hides for crafting |
| Hill Giants | Edgeville Dungeon | Big bones, 15 XP each |

### Prayer Points

- Prayer drains over time when active
- Recharge at altar (churches, POH)
- Prayer potions restore points

### Common Prayer Commands

```
TAB_OPEN prayer          - Open prayer tab
```

**Note:** Activating/deactivating prayers typically done via widget clicks, not dedicated commands.

### Efficient Training

1. **Kill monsters** → collect bones
2. **Inventory full** → `BURY_ALL`
3. **Repeat** until target level

Or for efficiency:
1. **Kill many monsters** → bank bones
2. **Use bones on altar** → 3.5x XP (members)
