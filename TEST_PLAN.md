# Manny Plugin Test Plan

## Priority 1: Core Skills Loop Testing

### 1. Fishing Loop (Shrimp)
- [x] Go to Draynor fishing spot
- [x] Fish shrimp until inventory full
- [ ] Bank fish at Draynor bank
- [ ] Repeat loop

### 2. Woodcutting Loop
- [x] Chop trees near Draynor
- [x] Bank logs
- [ ] Withdraw axe (if needed)
- [ ] Repeat loop

### 3. Cooking Test
- [ ] Withdraw raw fish from bank
- [ ] Withdraw tinderbox and logs
- [ ] Light fire (LIGHT_FIRE command?)
- [ ] Cook fish on fire
- [ ] Bank cooked fish

### 4. Mining Loop
- [ ] Go to mining location (Lumbridge?)
- [ ] Mine ore until inventory full
- [ ] Bank ore
- [ ] Repeat loop

### 5. Smithing Test
- [ ] Withdraw ore from bank
- [ ] Go to furnace
- [ ] Smelt bars
- [ ] Bank bars

## Priority 2: Interaction Reliability

### Right-Click Menu Issues
Current stats from logs show 10.7% success rate on menu clicks (29/270).
Issues observed:
- Menu position calculation off
- Clicking "Cancel" instead of target option
- Left-click verification mismatch ("Net" vs "Small Net")

**Investigation needed:**
- Record video of right-click menu interactions
- Compare calculated click positions vs actual menu positions
- Check if 2x UI scaling affects menu coordinate calculation

### Bank Interactions
- [ ] Test BANK_WITHDRAW with quantity (e.g., `BANK_WITHDRAW Logs 1`)
- [ ] Test BANK_DEPOSIT_ALL
- [ ] Test BANK_DEPOSIT_ITEM with quantity
- [ ] Verify bank detection (isBankOpen)

## Priority 3: Navigation

### Pathfinding
- [ ] Test long-distance navigation
- [ ] Test navigation around obstacles
- [ ] Test navigation near aggressive NPCs (avoid dark wizards)

### Known Issues
- Player wandered toward jail guards during woodcutting
- "No path found - stuck in" errors observed

## Priority 4: Combat (if applicable)

### Basic Combat
- [ ] Attack NPC
- [ ] Eat food when low HP
- [ ] Flee when HP critical

## Commands Reference

### Bank Commands
- `BANK_OPEN` - Open nearest bank
- `BANK_CLOSE` - Close bank interface
- `BANK_WITHDRAW <item> [qty]` - Withdraw item (qty=-1 or omit for all)
- `BANK_DEPOSIT_ALL` - Deposit entire inventory
- `BANK_DEPOSIT_ITEM <item> [qty]` - Deposit specific item

### Skill Commands
- `FISH <type>` - Fish until inventory full (e.g., FISH Shrimp)
- `CHOP_TREE [type]` - Chop trees until inventory full
- `MINE_ORE <type>` - Mine ore until inventory full

### Movement
- `GOTO <x> <y> <plane>` - Walk to coordinates
- `STOP` - Stop current action

## Test Results Log

| Date | Test | Result | Notes |
|------|------|--------|-------|
| 2024-12-18 | FISH Shrimp | PASS (after fix) | Changed "Net" to "Small Net" in CoreUtils.java |
| 2024-12-18 | CHOP_TREE | PARTIAL | Works but wanders toward dangerous areas |
| 2024-12-18 | BANK_DEPOSIT_ALL | PASS | Successfully deposited all items |
| 2024-12-18 | BANK_WITHDRAW | PASS | Works, but withdrew all instead of 1 (user error) |
