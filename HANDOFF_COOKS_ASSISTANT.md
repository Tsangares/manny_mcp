# Handoff: Complete Cook's Assistant Quest

## Current State
- **Location**: Lumbridge Castle kitchen (3206, 3216, 0) - standing next to the Cook
- **Inventory**: 27 Raw shrimps + 1 Gold bar (FULL - 28/28)
- **Quest Status**: NOT STARTED - need to talk to Cook and accept quest

## Objective
Complete Cook's Assistant quest so we can use the Lumbridge cooking range to cook ~1000 raw shrimps.

## Items Needed
1. **Egg** - 1
2. **Bucket of milk** - 1
3. **Pot of flour** - 1

## Recommended Approach: BUY FROM VARROCK

The user suggested buying items in Varrock rather than gathering them manually. This is faster.

### Step 1: Bank the shrimps first
```
GOTO 3208 3220 0           # Lumbridge bank stairs area
# Bank is upstairs (plane 2) - may need manual stair climb
# OR go to Draynor bank: GOTO 3092 3243 0
BANK_OPEN
BANK_DEPOSIT_ALL
```

### Step 2: Get money from bank
```
BANK_WITHDRAW coins 100    # Should be enough for items
BANK_CLOSE
```

### Step 3: Go to Varrock
```
GOTO 3212 3428 0           # Varrock center (or use Lumbridge->Varrock path)
```

### Step 4: Buy items
- **General Store** (3213, 3414): May have pot, bucket
- **Food Shop** (3166, 3308): May have egg
- Alternative: Grand Exchange has everything

### Step 5: Get flour (if not buyable)
- Buy empty pot
- Pick wheat at farm north of Lumbridge (3161, 3295)
- Use wheat on windmill hopper (3166, 3306)
- Operate controls, collect flour downstairs with pot

### Step 6: Get milk (if not buyable)
- Buy bucket
- Milk cow at Lumbridge farm (3253, 3270)

### Step 7: Return to Cook
```
GOTO 3207 3215 0           # Lumbridge kitchen
INTERACT_NPC Cook Talk-to
```

## Important Commands
```
GOTO x y plane             # Navigation
BANK_OPEN                  # Open nearest bank
BANK_WITHDRAW "item" qty   # Withdraw items (no quotes needed usually)
BANK_DEPOSIT_ALL           # Deposit everything
INTERACT_NPC name action   # Talk to NPCs
INTERACT_OBJECT name action # Use objects
```

## Known Issues & Workarounds

### 1. Dialogue clicking doesn't work automatically
- `send_input` clicks don't reach the game canvas
- **Workaround**: Ask user to click through dialogues manually
- Commands like `CLICK_DIALOGUE` exist but aren't reliable

### 2. Plane changes (stairs)
- `GOTO` can't handle plane changes automatically
- Lumbridge bank is on plane 2 (upstairs)
- **Workaround**: Use Draynor bank (plane 0) instead, or ask user to climb stairs

### 3. Combat system (FIXED)
- Previously attacked random events and quest NPCs
- Now filters by combat level > 0 AND has Attack action
- Should no longer interfere with Cook dialogue

## After Quest Completion
Once quest is done:
```
INTERACT_OBJECT Range Cook    # Opens cooking interface
# User clicks to cook all
```

Then cook all ~1000 raw shrimps from bank in batches of 27.

## Files to Reference
- `/home/wil/manny-mcp/journals/cooking_quest_2025-12-21.md` - Session notes
- `/home/wil/manny-mcp/BUG_REPORTS.md` - Known bugs documented
- `/home/wil/manny-mcp/CLAUDE.md` - Full MCP documentation
