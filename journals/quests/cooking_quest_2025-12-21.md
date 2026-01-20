# Session Journal - 2025-12-21

## Goal
Cook raw shrimps to level up Cooking, but needed Cook's Assistant quest first to use Lumbridge range.

## What Happened

### Cooking Attempt
- Had 27 raw shrimps in inventory, navigated to Lumbridge kitchen
- `COOK_ALL` command only searches for "Fire" objects, not "Range"
- Used `INTERACT_OBJECT Range Cook` - worked! But Cook said "Hey, who said you could use that?"
- Need to complete Cook's Assistant quest first

### Quest Dialogue Issues
- Started talking to Cook for the quest
- **Problem**: `send_input` clicks don't reach the game canvas
- The MCP tool reports success but nothing happens in-game
- User had to click dialogue manually

### Combat System Interference
- Random event NPC "Capt' Arnav" appeared
- Combat system detected him as a "threat" and tried to attack
- He's level 0 with no Attack option - can't be attacked
- Combat system also triggered on the Cook NPC during dialogue
- **Root cause**: `getAttackerDirect()` returns ANY NPC interacting with player, doesn't check if attackable

## Bugs Found & Documented

### 1. Combat System (HIGH priority)
**File**: `CombatSystem.java:1647-1669`
**Fix**: Add `&& npc.getCombatLevel() > 0` check
```java
if (target != null && target.equals(player) && npc.getCombatLevel() > 0)
```

### 2. Missing Input Commands (MEDIUM)
- No `CLICK x y` command for raw positional clicks
- No `KEY keyname` command for keyboard input
- `CLICK_WIDGET` has text search stub but says "not yet implemented"

### 3. COOK_ALL Only Finds Fires
- Doesn't work with cooking ranges
- Workaround: Use `INTERACT_OBJECT Range Cook` instead

## What Works Well
- `INTERACT_OBJECT Range Cook` - successfully clicked the range
- `GOTO` navigation - got to Lumbridge kitchen fine
- `BANK_WITHDRAW` - got 27 raw shrimps from Draynor bank
- `SCAN_WIDGETS` exists for finding UI elements

## Key Learnings
- Mouse/Keyboard classes exist in `/human/` directory
- `mouse.click(x, y, right)` dispatches AWT events to canvas
- `keyboard.pressKey(keyName)` for key presses
- Widget text search would be ideal for dialogue automation
- Combat system needs smarter target filtering

## Next Steps
1. Fix combat system NPC filtering (one-line fix)
2. Add CLICK/KEY commands to PlayerHelpers
3. Implement widget text search for dialogue clicking
4. Complete Cook's Assistant quest
5. Then cook the shrimps

## Session Stats
- Cooking: 17 (unchanged - couldn't cook yet)
- Fishing: 39
- Raw shrimps in inventory: 27
- Location: Lumbridge Castle kitchen
