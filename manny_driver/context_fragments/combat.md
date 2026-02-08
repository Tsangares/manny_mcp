## Combat Context

### KILL_LOOP - The Primary Combat Command
```
KILL_LOOP <npc> <food> [count]

Examples:
  KILL_LOOP Giant_frog none 100     # No food, kill 100
  KILL_LOOP Cow Tuna 50             # Eat tuna when low HP
  KILL_LOOP Chicken none            # Default 100 kills
```

### NPC Name Format
Use underscores for multi-word names: `Giant_frog`, `Dairy_cow`, `Guard_dog`

### Food Management
- `none` = Don't eat, no food safety
- Specific food = Eats when HP drops below threshold
- Escape threshold: Returns to bank if food count < 3

### Combat Styles (NOTE: Manual switching may be needed)
The default combat style trains ATTACK. For now, just start combat:
```
KILL_LOOP Chicken none 100    # Trains Attack by default
```

**NOTE**: SWITCH_COMBAT_STYLE is unreliable - the user may need to manually
change combat style in the game interface if training Strength or Defence.

**CRITICAL**: Send each command in a SEPARATE send_command() call!
Do NOT combine with semicolons - `cmd1; cmd2` will NOT work!

### Combat Setup Pattern (FOLLOW THIS ORDER)
1. **Observe**: get_game_state(fields=["location", "health", "skills"])
2. **Verify location**: Check coordinates match target area. Common spots:
   - Chickens: ~(3230, 3295) north of Lumbridge
   - Cows: ~(3253, 3270) east of Lumbridge
   - Giant frogs: ~(3195, 3169) Lumbridge swamp
3. **Navigate if needed**: Use GOTO to reach the combat area FIRST
4. **Switch combat style**: SWITCH_COMBAT_STYLE based on skill to train
5. **Start combat**: KILL_LOOP <npc> <food> [count]

**NEVER claim you're at a location without checking coordinates!**

### Safety
- STOP command halts all activity immediately
- Bot auto-returns to bank if HP critical and no food
- Check get_logs(grep="COMBAT") if loop stops unexpectedly
