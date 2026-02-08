## Skilling Context

### Key Insight: Fishing Spots are NPCs, Not Objects!
OSRS fishing spots appear as NPCs in the game engine. This is a common source of confusion.

| Activity | Spot Type | Discovery Tool | Interaction Command |
|----------|-----------|----------------|---------------------|
| Net fishing | NPC ("Fishing spot") | query_nearby(include_npcs=True) | FISH or INTERACT_NPC Fishing_spot Net |
| Rod fishing | NPC ("Fishing spot") | query_nearby(include_npcs=True) | INTERACT_NPC Fishing_spot Bait |
| Mining | Object (Rock) | query_nearby(include_objects=True) | INTERACT_OBJECT Rock Mine |
| Woodcutting | Object (Tree) | query_nearby(include_objects=True) | CHOP_TREE |

### Discovery Pattern
1. **Check equipment first**: get_game_state(fields=["inventory", "equipment"])
2. **Find activity spot**: query_nearby() with appropriate filters
3. **Execute**: Use the correct command based on spot type

### Equipment Requirements
| Activity | Required Tool | Check With |
|----------|--------------|------------|
| Net fishing | Small fishing net | get_game_state(fields=["inventory"]) |
| Rod fishing | Fishing rod + bait | get_game_state(fields=["inventory"]) |
| Mining | Any pickaxe (inv OR equipped) | get_game_state(fields=["inventory", "equipment"]) |
| Woodcutting | Any axe (inv OR equipped) | get_game_state(fields=["inventory", "equipment"]) |

### Static Item Spawns (fishing nets, buckets, etc.)
Permanent respawning items are GameObjects, not TileItems:
- **WRONG**: query_nearby(include_ground_items=True) - finds nothing
- **CORRECT**: scan_tile_objects(object_name="fishing net")
- **Pick up**: INTERACT_OBJECT small_fishing_net Take

### Fishing Commands
```
FISH <fish_type>        - Fish specific type (lowercase)
                          Examples: FISH shrimp, FISH lobster, FISH swordfish
FISH                    - Fish at current spot (uses default method)
FISH_DRAYNOR_LOOP       - Shrimp fishing + bank loop at Draynor
```

**IMPORTANT:** Use lowercase fish type: `FISH shrimp` not `FISH Shrimp`

**Why FISH command is preferred:**
- Handles fishing spot movement automatically (spots relocate periodically)
- Re-clicks spots when needed
- Simpler than INTERACT_NPC

**When to use INTERACT_NPC:** Only if FISH doesn't work or you need specific rod/bait action.
