## Shop Context

**STATUS: NEEDS TESTING** - Commands exist but workflow needs verification.

### Shop Commands

```
SHOP_BUY <item> <quantity>    - Buy item from open shop
```

### Opening Shops

```python
# Find shopkeeper
query_nearby(include_npcs=True, name_filter="shop")

# Trade with shopkeeper
send_command("INTERACT_NPC Shopkeeper Trade")
```

### Common Shops (F2P)

| Shop | Location | Sells |
|------|----------|-------|
| Lumbridge General Store | 3211, 3247, 0 | Basic supplies |
| Al Kharid General Store | 3315, 3180, 0 | Basic supplies |
| Varrock Sword Shop | TODO | Bronze-steel swords |
| Port Sarim Fishing Shop | 3014, 3224, 0 | Fishing supplies |
| Falador Shield Shop | TODO | Shields |

### Shop Workflow

```python
# 1. Travel to shop
send_command("GOTO 3211 3247 0")  # Lumbridge general store

# 2. Open shop interface
send_command("INTERACT_NPC Shop_keeper Trade")

# 3. Buy items
send_command("SHOP_BUY Bucket 1")
send_command("SHOP_BUY Pot 1")

# 4. Close shop (Escape or click X)
send_command("KEY_PRESS Escape")
```

### Shop Widget Clicking

For specific shop interactions:
```python
send_command('CLICK_WIDGET <shop_widget_id> "Buy 1"')
send_command('CLICK_WIDGET <shop_widget_id> "Buy 10"')
```

**TODO:** Document:
- Shop widget IDs
- Buy quantity options (1, 5, 10, 50, X)
- Sell workflow
- Stock respawn mechanics

### Shops vs GE

| Feature | Shops | Grand Exchange |
|---------|-------|----------------|
| Availability | Everywhere | GE only |
| Prices | Fixed (mostly) | Player-driven |
| Stock | Limited, respawns | Unlimited (if listed) |
| F2P access | All shops | 3 GE slots |

### Verification Needed

To properly document this fragment, test:
1. `SHOP_BUY` command format and behavior
2. Shop widget IDs
3. Sell to shop workflow
4. Different shop locations
