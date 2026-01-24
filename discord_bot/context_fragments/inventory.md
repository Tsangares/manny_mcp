## Inventory Management Context

### DROP vs BANK - Critical Distinction!

| Command | Effect | Reversible? |
|---------|--------|-------------|
| `DROP_ALL` | Items fall on ground | NO - items despawn! |
| `DROP_ITEM <item>` | Drop one item | NO - items despawn! |
| `BANK_DEPOSIT_ALL` | Items go to bank | YES - retrieve anytime |

**NEVER use DROP when user means BANK!**

### Dropping Items

```
DROP_ALL                - Drop EVERYTHING in inventory (dangerous!)
DROP_ALL <item>         - Drop all of specific item (e.g., DROP_ALL Bones)
DROP_ITEM <item>        - Drop one of an item
```

**Common use case:** Power training (drop fish/logs/ore to keep training)
```
DROP_ALL Raw_shrimps    - Drop all shrimps, keep fishing
DROP_ALL Logs           - Drop all logs, keep chopping
```

### Using Items

```
USE_ITEM_ON_ITEM <item1> <item2>     - Combine items (e.g., USE_ITEM_ON_ITEM Knife Logs)
USE_ITEM_ON_NPC <item> <npc>         - Use item on NPC (e.g., USE_ITEM_ON_NPC Bucket Dairy_cow)
USE_ITEM_ON_OBJECT <item> <object>   - Use item on object (e.g., USE_ITEM_ON_OBJECT Grain Hopper)
```

### Equipment

```
EQUIP_BEST_MELEE        - Auto-equip best melee gear from inventory
```

**Manual equipping:** Click item in inventory (handled by widget clicks, not commands)

### Picking Up Items

**Two systems - know the difference!**

| Item Type | Discovery | Pickup Command |
|-----------|-----------|----------------|
| Dropped items (loot) | `query_nearby(include_ground_items=True)` | `PICK_UP_ITEM <item>` |
| Static spawns (nets, buckets) | `scan_tile_objects(object_name="X")` | `INTERACT_OBJECT <name> Take` |

### Inventory Queries

```
get_game_state(fields=["inventory"])      - Compact view (names + quantities)
get_game_state(fields=["inventory_full"]) - Full details (slots, IDs, actions)
QUERY_INVENTORY                           - Plugin command for inventory state
```

### Naming Conventions

- **Items use spaces:** `Raw shrimps`, `Pot of flour`, `Small fishing net`
- **In commands, some need underscores:** Check specific command docs

### Common Patterns

**Power fishing (drop fish):**
```python
send_command("FISH shrimp")
# When inventory full...
send_command("DROP_ALL Raw_shrimps")
send_command("FISH shrimp")
```

**Banking loop:**
```python
send_command("FISH shrimp")
# When inventory full...
send_command("GOTO 3093 3244 0")  # Draynor bank
send_command("BANK_OPEN")
send_command("BANK_DEPOSIT_ALL")
send_command("BANK_CLOSE")
send_command("GOTO 3087 3227 0")  # Back to fishing
```
