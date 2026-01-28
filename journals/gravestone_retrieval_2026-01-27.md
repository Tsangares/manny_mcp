# Gravestone Retrieval - Lessons Learned
**Date:** 2026-01-27

## The Problem

After dying to Dark Wizards and escaping Death's Domain, needed to retrieve items from gravestone before 15-minute timer expired. Initial scans for "grave" using `scan_tile_objects` failed repeatedly.

## Root Cause

1. **Gravestone appears as NPC, not GameObject** - The gravestone is detected by `query_nearby` as an NPC entry, NOT a tile object
2. **scan_tile_objects doesn't find it** - Because it's not in the standard object categories
3. **Time pressure** - 15-minute timer creates urgency; wasted time scanning wrong object types

## Key Lessons

### 1. Use query_nearby to Find Gravestones

**What happened:** `scan_tile_objects(object_name="grave")` returned "not found" repeatedly.
**Why:** Gravestone is registered as an NPC-like entity with actions, not a standard GameObject.
**Solution:**
```python
# BAD - Gravestones are not tile objects
scan_tile_objects("grave")  # Returns: not found

# GOOD - Query nearby includes NPC-like entities
query_nearby(include_npcs=True)
# Returns: {"name": "Grave", "actions": ["Check", "Loot"], "location": "WorldPoint(...)"}
```

### 2. Interact Using INTERACT_NPC

**What happened:** Found grave at (3216, 3365) via query_nearby.
**Solution:**
```python
# Grave has NPC-style interaction
send_command("INTERACT_NPC Grave Loot")  # Successfully loots all items
```

### 3. Gravestone Location = Death Location

**Key insight:** Gravestone spawns at exact death coordinates. If you died to Dark Wizards south of Varrock, the grave is in that dangerous area.

**Navigation tip:**
- Check location history for death coordinates
- Navigate quickly (Dark Wizards will attack)
- Loot and teleport home immediately

### 4. Timer Pressure Strategy

**What happened:** Had ~9 minutes on timer, client crashed, lost time restarting.
**Lesson:** Don't waste time on wrong approaches - if `scan_tile_objects` fails, immediately try `query_nearby`.

## Detection Pattern

```python
# Check for nearby grave
nearby = query_nearby(include_npcs=True)
for npc in nearby["npcs"]:
    if npc["name"] == "Grave":
        grave_loc = npc["location"]  # WorldPoint(x=3216, y=3365, plane=0)
        # Navigate and loot
        send_command(f"GOTO {x} {y} {plane}")
        send_command("INTERACT_NPC Grave Loot")
        break
```

## Items Successfully Retrieved

| Item | Type |
|------|------|
| Message | Quest item (Romeo and Juliet) |
| Cadava berries | Quest item (Romeo and Juliet) |
| Bronze axe, dagger, sword | Combat gear |
| Wooden shield, Shortbow | Combat gear |
| Bronze arrow x25 | Ammunition |
| Air/Mind/Water/Earth/Body runes | Magic supplies |

## Anti-Patterns

1. **Don't spam scan_tile_objects** - If it fails once, try query_nearby instead
2. **Don't linger in dangerous areas** - Loot and teleport immediately
3. **Don't assume object types** - Gravestones are NPC-like, not GameObjects

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `query_nearby(include_npcs=True)` | Find gravestone (appears as NPC) |
| `get_game_state(fields=["location"])` | Verify position |
| `INTERACT_NPC Grave Loot` | Retrieve all items |
| `TELEPORT_HOME` | Escape dangerous area after looting |

## Time Lost

**~5 minutes** scanning with wrong tool before discovering query_nearby works.

## Critical Takeaway

**Gravestones appear as NPCs in the OSRS engine, not as GameObjects.** Always use `query_nearby(include_npcs=True)` to find them, and `INTERACT_NPC Grave Loot` to retrieve items.
