# Ticket: Superheat Steel Bars Routine - Testing & Deployment

**Created:** 2026-02-05
**Status:** Ready for Testing
**Priority:** High

---

## Summary

Implemented a fully automated superheat steel bars routine that runs without LLM intervention. The routine mines coal and iron ore in the Mining Guild, casts Superheat Item to create steel bars, and loops until out of nature runes.

---

## Changes Implemented

### 1. MINE_ORE Count Parameter
**File:** `manny_src/utility/PlayerHelpers.java`

Added optional count parameter to MINE_ORE command:
```
MINE_ORE coal       → Mine until inventory full (existing behavior)
MINE_ORE coal 2     → Mine exactly 2 coal, then stop (NEW)
```

Response now includes:
- `target_count`: The requested count (-1 if not specified)
- `target_reached`: Boolean indicating if target was reached
- `inventory_full`: Boolean indicating if inventory is full

### 2. CMDLOG Loop Markers
**File:** `manny_src/utility/PlayerHelpers.java`

Added `LOOP_START` and `LOOP_END` markers for inner loops with exit conditions:

```
LOOP_START exit_on:<condition>
  [commands...]
LOOP_END
```

**Supported exit conditions:**
| Condition | Description |
|-----------|-------------|
| `no_item:<name>` | Exit when item NOT in inventory |
| `has_item:<name>` | Exit when item IS in inventory |
| `inventory_full` | Exit when inventory is full |
| `inventory_empty` | Exit when inventory is empty |

### 3. Superheat Steel Loop CMDLOG
**File:** `/home/wil/osrs_scenarios/superheat_steel_loop.cmdlog`

Complete routine for superheating steel bars in Mining Guild.

---

## Testing Checklist

### Pre-requisites
- [ ] Gamescope displays running (`./start_gamescopes.sh status`)
- [ ] Account has 60+ Mining (Mining Guild requirement)
- [ ] Account has 43+ Magic (Superheat Item requirement)
- [ ] Account has 30+ Smithing (Steel bar requirement)

### Equipment Setup
- [ ] Staff of fire **equipped** (provides unlimited fire runes)
- [ ] Pickaxe **equipped** (bronze+ works, rune recommended)
- [ ] Nature runes in **bank** (will withdraw 25 per trip)

### Test Sequence

#### Test 1: MINE_ORE with Count
```python
# Start RuneLite
start_runelite(account_id="main")

# Navigate to any mining spot
send_command("GOTO 3037 9737 0")  # Mining Guild coal

# Test mining exactly 2 coal
send_command("MINE_ORE coal 2")

# Verify in logs:
get_logs(grep="MINE_ORE", since_seconds=60)
# Expected: "Reached target count of 2 ore(s), stopping"
```

#### Test 2: CAST_SPELL_ON_INVENTORY_ITEM
```python
# With iron ore in inventory
send_command("KEY_PRESS F6")  # Open magic tab
send_command("CAST_SPELL_ON_INVENTORY_ITEM Superheat_Item Iron_ore")

# Verify:
# - Magic tab opens
# - Spell is clicked
# - Iron ore is clicked
# - Steel bar created (if 2+ coal in inventory)
```

#### Test 3: Full CMDLOG Routine
```python
# Position: Already inside Mining Guild (underground)
# Inventory: Nature runes, empty slots for ore/bars

send_command("LOAD_CMDLOG superheat_steel_loop")

# Monitor:
get_logs(grep="CMDLOG", since_seconds=300)
# Expected: Loop iterations, exit condition checks
```

### Expected Behavior
1. F2P_MODE enabled (blocks P2P pathing)
2. Camera stabilized (pitch=350, zoom in)
3. Loop starts:
   - Walk to coal rocks (3037, 9737)
   - Mine 2 coal (stops after exactly 2)
   - Walk to iron rocks (3029, 9739)
   - Mine 1 iron
   - Press F6 (magic tab)
   - Cast Superheat Item on Iron ore
   - Repeat
4. Loop exits when no Nature rune in inventory

---

## Known Limitations

1. **Banking not included** - The CMDLOG only handles the mining/superheating loop. Banking must be done manually or via a separate routine.

2. **Starting position** - Must already be inside Mining Guild (underground) before running.

3. **F2P coordinates only** - Uses F2P section of Mining Guild:
   - Coal: (3037, 9737, 0)
   - Iron: (3029, 9739, 0)
   - These are validated F2P coordinates.

4. **Ring of Forging not used** - Iron has ~50% success rate without ring. Steel bars always succeed if you have the materials.

---

## Full Workflow (Including Banking)

For a complete session, combine with banking:

```python
# 1. Start at Falador East Bank
send_command("GOTO 3012 3355 0")
send_command("BANK_OPEN")
send_command("BANK_DEPOSIT_ALL")
send_command("BANK_WITHDRAW Nature_rune 25")
send_command("BANK_CLOSE")

# 2. Travel to Mining Guild
send_command("GOTO 3019 3339 0")
send_command("INTERACT_OBJECT Ladder Climb-down")

# 3. Run the loop
send_command("LOAD_CMDLOG superheat_steel_loop")

# 4. When loop exits (out of natures), return to bank
send_command("GOTO 3019 9739 0")
send_command("INTERACT_OBJECT Ladder Climb-up")
# Repeat from step 1
```

---

## Future Improvements

1. **Full banking CMDLOG** - Create a wrapper CMDLOG that includes banking phase

2. **Batch mining mode** - Mine all coal/iron first, then superheat in batches (more efficient)

3. **Ring of Forging support** - Auto-equip ring before superheating iron

4. **XP tracking** - Log XP gains per loop iteration

5. **Error recovery** - Auto-restart if interrupted by random events

---

## Files Modified

| File | Changes |
|------|---------|
| `manny_src/utility/PlayerHelpers.java` | MINE_ORE count param, CMDLOG loop markers |
| `/home/wil/osrs_scenarios/superheat_steel_loop.cmdlog` | New routine file |

---

## Rollback

If issues arise, the changes are isolated to:
1. `handleMineOre()` method - count parsing and loop condition
2. `parseCmdlogFile()` method - LOOP_START/LOOP_END parsing
3. `executeCmdlogSequence()` method - loop execution logic
4. New helper methods: `findLoopEnd()`, `checkLoopExitCondition()`, `executeSingleCommand()`

To rollback, revert changes in `PlayerHelpers.java` and delete the CMDLOG file.
