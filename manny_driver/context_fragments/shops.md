## Shop Context

**STATUS: VERIFIED** - SHOP_BUY command tested and working.

### Shop Commands

```
SHOP_BUY <item> <quantity>    - Buy item from open shop
```

**Example:**
```python
send_command("SHOP_BUY Pot 1")      # Buy 1 pot
send_command("SHOP_BUY Bucket 5")   # Buy 5 buckets
```

### Opening Shops

```python
# Find shopkeeper
query_nearby(include_npcs=True, name_filter="shop")

# Trade with shopkeeper (use underscore for multi-word names)
send_command("INTERACT_NPC Shop_keeper Trade")
# or
send_command("INTERACT_NPC Shop_assistant Trade")
```

### Shop Widget IDs (VERIFIED - Group 300)

| Widget | ID | Purpose |
|--------|----|---------|
| Container | 19660800 | Main shop window |
| Title | 19660801 | Shop name (e.g., "Varrock General Store") |
| Close | 19660801 (nested 11) | Close button |
| Item area | 19660816 | Contains shop items |
| Value | 19660805 | Check item value |
| Buy-1 | 19660808 | Buy 1 of selected item |
| Buy-5 | 19660810 | Buy 5 of selected item |
| Buy-10 | 19660812 | Buy 10 of selected item |
| Buy-50 | 19660814 | Buy 50 of selected item |

### Item Widgets in Shops

Items appear as children of widget 19660816 with:
- `text`: Item name (e.g., "Pot")
- `itemId`: Game item ID (e.g., 1931 for Pot)
- `itemQuantity`: Stock quantity
- `actions`: ["Value", "Buy 1", "Buy 5"]

```python
# Find items in shop
find_widget(text="Pot")
# Returns: itemId, itemQuantity, actions
```

### Shop Workflow (VERIFIED)

```python
# 1. Travel to shop
send_command("GOTO 3196 3431 0")  # Near Varrock general store

# 2. Open shop interface
send_command("INTERACT_NPC Shop_keeper Trade")

# 3. Buy items (VERIFIED - works correctly)
send_command("SHOP_BUY Pot 1")     # Buys 1 pot
send_command("SHOP_BUY Pot 3")     # Buys 3 pots

# 4. Close shop
send_command("CLOSE_INTERFACE")
```

### Common Shops (F2P)

| Shop | Location | NPC | Sells |
|------|----------|-----|-------|
| Varrock General Store | 3217, 3416, 0 | Shop keeper | Basic supplies |
| Lumbridge General Store | 3211, 3247, 0 | Shop keeper | Basic supplies |
| Al Kharid General Store | 3315, 3180, 0 | Shop keeper | Basic supplies |
| Port Sarim Fishing Shop | 3014, 3224, 0 | Gerrant | Fishing supplies |

### Shops vs Grand Exchange

| Feature | Shops | Grand Exchange |
|---------|-------|----------------|
| Availability | Everywhere | GE only |
| Prices | Fixed (mostly) | Player-driven |
| Stock | Limited, respawns | Unlimited (if listed) |
| F2P access | All shops | 3 GE slots |
| Automation | SHOP_BUY works | GE_BUY/GE_SELL work |

### Tips

- Use underscore for NPC names: `Shop_keeper` not `Shop keeper`
- SHOP_BUY handles any quantity (tested with 1 and 3)
- Close shop with `CLOSE_INTERFACE`
- Check stock with `find_widget(text="item_name")` to see `itemQuantity`

### TODO

- Test selling items to shops
- Test specialty shops (weapon shops, magic shops)
- Test stock respawn detection
