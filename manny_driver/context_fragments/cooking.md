## Cooking Context

### Cooking Commands

```
COOK_ALL                - Cook all raw food in inventory on nearest range/fire
```

### Cooking Workflow

1. **Get raw food** (fishing, buying, etc.)
2. **Find cooking spot** (range or fire)
3. **Cook:** `COOK_ALL`

### Cooking Locations

| Location | Type | Coordinates |
|----------|------|-------------|
| Lumbridge Castle Kitchen | Range | 3211, 3216, 0 |
| Al Kharid | Range | 3273, 3180, 0 |
| Rogues' Den | Eternal fire | 3043, 4973, 1 |

### Finding Cooking Spots

```python
# Find a range
query_nearby(include_objects=True, name_filter="range")

# Interact with range (for manual cooking)
send_command("INTERACT_OBJECT Cooking_range Cook")
```

### Raw → Cooked Items

| Raw Item | Cooked Item | Level |
|----------|-------------|-------|
| Raw shrimps | Shrimps | 1 |
| Raw anchovies | Anchovies | 1 |
| Raw trout | Trout | 15 |
| Raw salmon | Salmon | 25 |
| Raw lobster | Lobster | 40 |
| Raw swordfish | Swordfish | 45 |

### Cooking + Fishing Loop

```python
# At Draynor
send_command("FISH shrimp")
# Wait for full inventory...
send_command("GOTO 3211 3216 0")  # Lumbridge kitchen
send_command("COOK_ALL")
# Wait for cooking...
send_command("BANK_OPEN")
send_command("BANK_DEPOSIT_ALL")
```

### Burn Rates

Lower cooking level = higher burn chance. Use:
- **Cooking gauntlets** (reduces burn rate)
- **Hosidius range** (reduces burn rate after favor)
- **Higher level** (eventually stop burning)

### Common Issues

- **"Nothing to cook"** → No raw food in inventory
- **Burning food** → Level too low, cook lower-tier food
- **Can't find range** → Use `query_nearby` to scan for cooking spots
