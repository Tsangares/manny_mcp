# Cooking Routine Development Journal - 2025-01-04

## Session Goal
Build and test a YAML routine for cooking raw fish at Lumbridge Castle range.

## Session Summary
Successfully completed one full cooking trip: bank → stairs → range → cook → stairs → bank.

## Results
- **Starting level**: Cooking 18 (3,610 XP)
- **Ending level**: Cooking 19 (4,330 XP)
- **XP gained**: 720 XP
- **Fish cooked**: ~24 Shrimps from 27 Raw shrimps
- **Burnt**: ~3 Burnt shrimp (~11% burn rate)

## Key Learnings

### 1. Object vs Item Naming Convention
| Type | Convention | Example |
|------|------------|---------|
| Objects | Underscores | `Cooking_range`, `Large_door` |
| Items | Spaces | `Raw shrimps`, `Pot of flour` |

**Critical**: The cooking range is called `Cooking_range` (with underscore), NOT `Range`!

### 2. Use Southern Staircase Exclusively
- **Southern stairs**: (3204, 3207) on plane 0 - RIGHT NEXT TO KITCHEN
- Northern stairs: (3204, 3229) - far from kitchen, requires walking through dining room

Using the southern staircase eliminates the need to navigate through the castle interior.

### 3. Cooking Workflow
```
1. INTERACT_OBJECT Cooking_range Cook  (opens interface)
2. KEY_PRESS Space                      (confirms "Cook All")
3. await no_item:Raw shrimps            (wait for completion)
```

**Note**: `USE_ITEM_ON_OBJECT` did NOT work for cooking. Use `INTERACT_OBJECT` instead.

### 4. Level-Up Dialogues Interrupt Cooking
When you level up mid-cooking:
- Cooking animation stops
- Dialogue appears ("Congratulations, you just advanced...")
- Press Space to dismiss
- Must re-click range to cook remaining items

### 5. Indoor Navigation Protocol
**Never blindly GOTO through walls!**

Before indoor navigation:
1. Scan for doors: `scan_tile_objects("door")`
2. Identify correct door (Large_door vs Door vs Trapdoor)
3. Open door: `INTERACT_OBJECT Large_door Open`
4. Then walk to destination

### 6. Pathfinding Limitations
The naive pathfinding gets stuck on:
- Walls
- Closed doors
- Multi-room buildings

Solution: Break path into segments, open doors manually.

## Pitfalls Encountered

### Trapped in Wrong Room
- Entered dining room through wrong door
- Got stuck trying to reach range
- Solution: Exit the way you came, find correct path

### Object Name Mismatches
- `Range` - NOT FOUND
- `Cooking range` - NOT FOUND (spaces don't work for objects)
- `Cooking_range` - SUCCESS!

### USE_ITEM_ON_OBJECT Failures
- `USE_ITEM_ON_OBJECT Raw shrimps Range` - Failed
- `USE_ITEM_ON_OBJECT Raw_shrimps Range` - Failed (wrong item name format)
- Solution: Use `INTERACT_OBJECT Cooking_range Cook` instead

## Working Routine

### MCP Commands (One Trip)
```python
# Bank phase
send_command("BANK_OPEN")
send_command("BANK_WITHDRAW Raw shrimps 27")
send_command("BANK_CLOSE")

# Navigate down (southern stairs)
send_and_await("INTERACT_OBJECT Staircase Climb-down", "plane:1")
send_and_await("INTERACT_OBJECT Staircase Climb-down", "plane:0")

# Cook
send_command("INTERACT_OBJECT Cooking_range Cook")
time.sleep(1)  # Wait for interface
send_command("KEY_PRESS Space")
await_state_change("no_item:Raw shrimps", timeout_ms=60000)

# Navigate up (southern stairs)
send_and_await("INTERACT_OBJECT Staircase Climb-up", "plane:1")
send_and_await("INTERACT_OBJECT Staircase Climb-up", "plane:2")

# Deposit
send_command("BANK_OPEN")
send_command("BANK_DEPOSIT_ALL")
send_command("BANK_CLOSE")
```

## Files Updated
- `routines/skilling/cooking_lumbridge.yaml` - Full routine with all learnings
- `CLAUDE.md` - Added Indoor Navigation Protocol section

## Next Steps
1. Test full loop (multiple trips)
2. Add level-up dialogue handling
3. Test with Raw anchovies
4. Consider adding error recovery for disconnections

## Stats
- **Session duration**: ~30 minutes
- **Trips completed**: 1
- **Routine status**: Validated and working
