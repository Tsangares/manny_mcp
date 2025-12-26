# Cook's Assistant Quest - Command Log

## Quest Progress

### Items Required
- [x] Egg - Given to Cook
- [ ] Bucket of milk - Need bucket + dairy cow
- [ ] Pot of flour - Have pot, need wheat + windmill

### Current Status
- **Location**: (3256, 3226, 0) - Near Lumbridge
- **Inventory**: Pot

## Commands Used

### 1. Navigate to Cook
```
GOTO 3208 3216 0
```
Navigates to Lumbridge Castle kitchen where the Cook is located.

### 2. Talk to Cook
```
INTERACT_NPC Cook Talk-to
```
Starts quest dialogue. The Cook asks for three ingredients.

### 3. Dialogue Interaction
- Used manual click on "Click here to continue" button (coordinates ~370, 783)
- Alternatively, spacebar key advances dialogue
- Gave Egg to Cook during dialogue (1/3 items complete)

### 4. Navigate to Cow Pen
```
GOTO 3253 3270 0
```
Navigates to dairy cow area east of Lumbridge.

## Bucket Locations (from OSRS Wiki)

According to [Cook's Assistant - OSRS Wiki](https://oldschool.runescape.wiki/w/Cook's_Assistant) and [Quick Guide](https://oldschool.runescape.wiki/w/Cook's_Assistant/Quick_guide):

1. **Lumbridge Castle cellar** (most reliable spawn) - requires going down stairs
2. **Lumbridge General Store** (purchase for 2 coins) - at (3212, 3247, 0)
3. **Cow field northeast of Lumbridge** (ground spawn)
4. **Farm house near chickens** (Gillie Groats' house)

### Bucket Acquisition - BLOCKER

**Methods Attempted**:
1. **PICK_UP_ITEM Bucket**: Command exists and works, but returns "Item not on ground: Bucket"
   - Tried at: Gillie Groats' house (3252, 3270, 0), Castle cellar area, Cow pen
   - Root cause: Ground item spawns are empty or despawned
2. **Shop purchase via send_input**: Opened shop interface, clicked bucket widget
   - Used: `INTERACT_NPC Shop_keeper Trade` then `send_input click` on bucket item
   - Result: Shop opened successfully, but clicking bucket widget didn't add to inventory
   - Root cause: Manual widget clicking via send_input doesn't trigger shop purchase
3. **query_nearby tool**: Doesn't detect ground item spawns (only NPCs and game objects)

**Root Cause**: No SHOP_BUY command exists for purchasing from general stores. The BUY_GE command only works for Grand Exchange.

**Impact**: Cannot autonomously acquire bucket, blocking milk collection step.

**Solution**: Built SHOP_BUY command to purchase items from general stores

**Implementation Status**:
- ✅ SHOP_BUY command implemented (lines 9241-9242, handler at 21953-22139)
- ✅ Command validates and compiles successfully
- ❌ Shop interface not opening reliably with INTERACT_NPC
- ⚠️ Need to debug shop opening workflow before SHOP_BUY can be tested

**Commands Added**:
```
SHOP_BUY <item_name> [quantity]
```
Format: `SHOP_BUY Bucket` or `SHOP_BUY Bucket 5`

## Navigation / Obstacle Issues

**Issue 1: Gates and Fences**
- Pathfinding cannot auto-open gates/fences
- Navigation gets stuck at closed obstacles
- Manual workaround: Restart client, manually open gate, continue

**Issue 2: Long-Distance Navigation Stuck**
- Occurred during GOTO from (3253, 3274, 0) to wheat field (3162, 3293, 0)
- Player stuck at (3176, 3286, 0) - 14 tiles from target
- State: "NAVIGATING" but no movement for 60+ seconds
- Possible causes: Undetected obstacle, pathfinding algorithm limitation, or terrain issue
- Resolution: Client restart required

**Pattern Observed**: Navigation failures occur more frequently on:
- Routes crossing multiple terrain types (farm → field)
- Distances > 80 tiles
- Areas with many small obstacles

**Future Need**:
- MCP wrapper for `INTERACT_OBJECT` to handle obstacles autonomously
- Better pathfinding with intermediate waypoints for long distances
- Stuck detection and auto-recovery mechanisms

## Progress Update (Session 2)

### Completed
- ✅ Picked wheat successfully (have Grain in inventory)
- ✅ Have Pot in inventory

### Current Blockers

**Flour Making - BLOCKED**:
- Cannot enter windmill - INTERACT_OBJECT fails to find door
- No ladder climbing commands exist in plugin (need CLIMB_LADDER_UP, CLIMB_LADDER_DOWN)
- Flour process requires: Enter windmill → Climb 2 ladders up → Use grain on hopper → Operate hopper → Climb 2 ladders down → Use pot on flour bin

**Bucket Acquisition - BLOCKED**:
- Ground spawns empty at all locations
- Shop interaction broken (INTERACT_NPC fails for "Shop keeper"/"Shop assistant")
- SHOP_BUY command built but untested due to shop interaction issue

### Next Steps (Requires Command Development)

1. Build ladder climbing commands (CLIMB_LADDER_UP, CLIMB_LADDER_DOWN)
2. Fix INTERACT_OBJECT to properly find windmill door
3. OR: Build complete MAKE_FLOUR command that handles the entire windmill process
4. Fix INTERACT_NPC for shop NPCs OR find alternative bucket source
5. Complete flour and milk collection
6. Return to Cook with all items

## Notes

- State file becomes stale after ~4-5 minutes of continuous navigation
- Client requires periodic restarts
- Multi-floor navigation (GOTO with different plane) doesn't work reliably
- PICKUP_ITEM command returns "Unknown command" error
