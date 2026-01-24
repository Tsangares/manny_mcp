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

### Combat Styles
```
SWITCH_COMBAT_STYLE <style>

Styles:
  Accurate    - Train Attack
  Aggressive  - Train Strength
  Defensive   - Train Defence
  Controlled  - Train all evenly
```

### Discovery Pattern
1. **Observe**: get_game_state(fields=["location", "health", "combat"])
2. **Check HP**: Ensure healthy enough for combat
3. **Find location**: lookup_location(location="<target_name>")
4. **Execute**: send_command(command="KILL_LOOP ...")

### Safety
- STOP command halts all activity immediately
- Bot auto-returns to bank if HP critical and no food
- Check get_logs(grep="COMBAT") if loop stops unexpectedly
