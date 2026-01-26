# Mining Commands Stuck & Bank Command Issues

**Date:** 2026-01-25
**Severity:** High (blocks automation)

## Issue 1: Mining Commands (POWER_MINE, MINE_ORE) Stuck

### Symptoms
- `POWER_MINE` and `MINE_ORE` commands start but never progress
- Log shows only "Starting intelligent power mining..." or "Starting to mine X until inventory full..."
- No subsequent logging (no inventory check, no rock search, nothing)
- Commands appear to hang indefinitely

### Root Cause Analysis
The commands call `MiningHelper.shouldDropInventory()` early in execution.
This calls `gameHelpers.getEmptySlots()` which calls:
1. `ensureInventoryOpen()` -> `isInventoryOpen()` -> `helper.readFromClient()`
2. `helper.readFromClient()` for inventory slot count

The `readFromClient()` method has a 5-second timeout, but NO timeout errors appear in logs.
This suggests either:
1. The callback is queued but never executed by the client thread
2. Some earlier blocking issue prevents the callback from completing
3. A silent exception is swallowed

### Expected Logging (not appearing)
```
[INVENTORY] Tab already open  (from isInventoryOpen())
[MINING] Inventory check: 28 empty slots, full=false  (from shouldDropInventory())
```

### Code Path
```
handleMineOre() or handlePowerMine()
  -> log.info("[MINE_ORE] Starting...")  // This appears
  -> CoreUtils.CoreConstants.getOreByName()
  -> new MiningHelper(...)
  -> miningHelper.shouldDropInventory()  // HANGS HERE
       -> gameHelpers.getEmptySlots()
            -> ensureInventoryOpen()
                 -> isInventoryOpen()
                      -> helper.readFromClient()  // ???
```

### Files to Investigate
- `manny_src/utility/PlayerHelpers.java:19685` (shouldDropInventory call)
- `manny_src/utility/PlayerHelpers.java:28425` (shouldDropInventory implementation)
- `manny_src/utility/GameEngine.java:636` (getEmptySlots)
- `manny_src/utility/GameEngine.java:329` (ensureInventoryOpen)
- `manny_src/utility/ClientThreadHelper.java:105` (readFromClient)

### Debugging Steps
1. Add explicit logging BEFORE each `readFromClient` call in the path
2. Check if client thread is blocked/overloaded
3. Check if game state updates (they do - state file is fresh)
4. Test if simpler commands using `readFromClient` work

---

## Issue 2: Wayland Mouse Permission Denied (informational)

### Symptoms
- POWER_MINE starts but doesn't actually mine anything
- Commands that require mouse movement silently fail
- User has to manually click on rocks/NPCs

### Root Cause
RuneLite running in gamescope/Xwayland is being blocked from using mouse control APIs:
```
!!! callRemoteDesktop:1189 Error: domain 541 code 0 message:
"GDBus.Error:org.freedesktop.DBus.Error.Failed: Session is not allowed to call NotifyPointer methods"
```

This error appears repeatedly in logs. The XDG RemoteDesktop portal is denying mouse control.

### Affected Commands
- POWER_MINE (can't click rocks)
- INTERACT_NPC (may fail to click)
- INTERACT_OBJECT (may fail to click)
- Any command using mouse movement

### Potential Fixes
1. **Use internal Java AWT events instead of system mouse**
   - The plugin's `Mouse` class should use `robot.mouseMove()` or direct AWT events
   - These work within the Java application without needing system-level mouse control

2. **Grant RemoteDesktop permissions**
   - May need to configure XDG portal permissions for the gamescope session
   - Or use a different display server setup

3. **Check if gamescope has mouse passthrough issues**
   - Gamescope may need specific flags for mouse control

### Investigation Needed
- Check if `Mouse.java` uses Java Robot vs system mouse
- Check if the issue only occurs in gamescope (not Xvfb)
- Test with `--headless` mode to compare

---

## Issue 2: Bank Commands Not Working

### Symptoms
- `BANK_DEPOSIT` commands fail silently
- `BANK_WITHDRAW` commands don't execute
- Log shows: `Command failed: BANK_DEPOSIT Iron ore 27`

### Observed Behavior
1. Bank interface opens successfully via `INTERACT_NPC Banker Bank`
2. `BANK_DEPOSIT_INVENTORY` - status unknown
3. `BANK_DEPOSIT <item> <qty>` - fails
4. `BANK_WITHDRAW <item> <qty>` - status unknown

### Possible Causes
1. **Mouse control blocked** (same as Issue 1)
   - If deposit/withdraw requires clicking widgets, blocked mouse = failure

2. **Widget targeting issue**
   - Bank item widgets may not be found correctly
   - Need to verify widget IDs are correct

3. **Command argument parsing**
   - Check if "Iron ore" (with space) parses correctly

### Commands to Test
```
BANK_DEPOSIT_INVENTORY
BANK_DEPOSIT Iron_ore 27
BANK_WITHDRAW Rune_pickaxe 1
```

### Logs to Check
```bash
grep -i "BANK\|deposit\|withdraw" /tmp/runelite_main.log | tail -50
```

---

## Related Files
- `manny_src/utility/Mouse.java` - Mouse control implementation
- `manny_src/utility/PlayerHelpers.java` - handleBankDeposit, handleBankWithdraw
- `manny_src/utility/CommandProcessor.java` - Command routing

## Priority
High - these issues block all automation that requires mouse interaction.
