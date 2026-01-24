## Grand Exchange Context

**STATUS: NEEDS TESTING** - Commands exist but workflow needs verification.

### GE Commands

```
BUY_GE <item> <quantity> <price>    - Buy item from GE
```

### GE Location

| Location | Coordinates |
|----------|-------------|
| Grand Exchange | 3165, 3487, 0 |

### GE Workflow (Theoretical)

```python
# 1. Travel to GE
send_command("GOTO 3165 3487 0")

# 2. Open GE interface
query_nearby(include_npcs=True, name_filter="Exchange")
send_command("INTERACT_NPC Grand_Exchange_Clerk Exchange")

# 3. Buy item
send_command("BUY_GE Lobster 100 200")  # 100 lobsters at 200gp each

# 4. Collect items
# TODO: Collection command/workflow
```

### GE Widget Clicking

The GE uses complex widget interfaces. May need:
```python
# Click specific GE buttons
send_command('CLICK_WIDGET <container_id> "<action>"')
```

**TODO:** Document:
- GE widget IDs for buy/sell slots
- Price adjustment buttons (+5%, -5%, etc.)
- Collect button workflow
- Abort offer workflow

### Common GE Items

| Category | Items |
|----------|-------|
| Food | Lobster, Swordfish, Shark |
| Runes | Law, Nature, Death, Blood |
| Potions | Strength potion, Prayer potion |
| Gear | Rune scimitar, Dragon items |

### GE Tips

- Check current prices before buying/selling
- Use price guide: `WebFetch` the wiki GE page
- GE has 8 slots (3 for F2P)

### Verification Needed

To properly document this fragment, test:
1. `BUY_GE` command format and behavior
2. Widget IDs for GE interface
3. Collection workflow after purchase
4. Selling items workflow
