## Interaction Context

### Entity Types and How to Interact

| Entity Type | Discovery Tool | Interaction Command |
|-------------|----------------|---------------------|
| NPCs (people, monsters, fishing spots) | query_nearby(include_npcs=True) | INTERACT_NPC <name> <action> |
| Objects (doors, trees, rocks, ranges) | query_nearby(include_objects=True) | INTERACT_OBJECT <name> <action> |
| Dropped items (loot, player drops) | query_nearby(include_ground_items=True) | PICK_UP_ITEM <name> |
| Static spawns (fishing nets, buckets) | scan_tile_objects(object_name="X") | INTERACT_OBJECT <name> Take |

### Naming Conventions
- **NPCs/Objects**: Use underscores for multi-word names
  - `Giant_frog`, `Large_door`, `Cooking_range`
- **Items**: Use spaces
  - `Raw shrimps`, `Pot of flour`

### Common Actions
| Entity | Common Actions |
|--------|----------------|
| NPCs | Talk-to, Attack, Trade, Pickpocket |
| Doors | Open, Close |
| Ladders/Stairs | Climb-up, Climb-down |
| Banks | Use, Bank |
| Cooking range | Cook |

### Ground Items - Two Types!
1. **TileItems (Dropped)**: Loot, player drops
   - Find: query_nearby(include_ground_items=True)
   - Pick up: PICK_UP_ITEM <item>

2. **GameObjects (Static Spawns)**: Permanent respawning items
   - Find: scan_tile_objects(object_name="<item>")
   - Pick up: INTERACT_OBJECT <item_name> Take

### Example: Pick Up Fishing Net Spawn
```
Step 1: scan_tile_objects(object_name="fishing net")
Result: {"objects": [{"name": "Small fishing net", "actions": ["Take"]}]}

Step 2: INTERACT_OBJECT small_fishing_net Take
```

### Using Items
```
USE_ITEM_ON_NPC <item> <npc>        # e.g., USE_ITEM_ON_NPC Bucket Dairy_cow
USE_ITEM_ON_OBJECT <item> <object>  # e.g., USE_ITEM_ON_OBJECT Grain Hopper
```
