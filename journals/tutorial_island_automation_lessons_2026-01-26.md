# Tutorial Island Automation - Lessons Learned
**Date:** 2026-01-26

## The Problem

Multiple failures while automating Tutorial Island sections 9-10 (Banking through Magic/Teleport). Key symptoms: mouse clicks landing on "Cancel" instead of targets, spells not casting, player not moving, and difficulty exiting the island.

## Root Causes

1. **CAST_SPELL_NPC calculates NPC bounds incorrectly when far away** - Returns negative Y coordinates (off-screen), causing clicks to miss
2. **GOTO uses minimap clicks that race with mouse movement** - Bezier mouse movement lands on wrong spot, clicks "Cancel"
3. **Multiple RuneLite clients on same display cause screenshot failures** - Window ID conflicts
4. **Home Teleport requires CAST_SPELL command** - Widget click alone doesn't trigger the spell

## Key Lessons

### 1. CAST_SPELL_NPC Requires Proximity

**What happened:** Spell wouldn't cast on chicken. Logs showed NPC bounds with y=-25 (off-screen).
**Why:** NPC model coordinates calculated incorrectly when player is far from target.
**Solution:**
```python
# BAD - Cast from far away, bounds off-screen
send_command("CAST_SPELL_NPC Wind_Strike Chicken")  # y=-25, clicks Cancel

# GOOD - Walk close first, then cast
send_command("GOTO 3139 3092 0")  # Walk near chickens
sleep(4)
send_command("CAST_SPELL_NPC Wind_Strike Chicken")  # Now bounds are valid
```

**Time wasted:** ~15 minutes debugging why clicks hit "Cancel"

### 2. Door Navigation Requires GOTO First

**What happened:** `INTERACT_OBJECT Door Open` clicked wrong door when multiple doors nearby.
**Why:** Command finds nearest matching object. Multiple doors in chapel area.
**Solution:**
```python
# BAD - Click nearest door (might be wrong one)
send_command("INTERACT_OBJECT Door Open")

# GOOD - Walk to specific door position first
send_command("GOTO 3123 3102 0")  # Position in front of correct door
sleep(3)
send_command("INTERACT_OBJECT Door Open")  # Now clicks the right door
```

**YAML pattern:**
```yaml
- id: 9
  action: GOTO
  args: "3124 3124 0"
  notes: "Walk to door position first"

- id: 10
  action: INTERACT_OBJECT
  args: "Door Open"
```

### 3. GOTO Fails When Minimap Click Misses

**What happened:** Player wouldn't move. Logs showed click landed on "Cancel" at wrong coordinates.
**Why:** `smartMinimapClick` uses Bezier mouse movement. Verification failed but clicked anyway.
**Solution:**
```python
# Check logs immediately when GOTO fails
get_logs(level="ALL", since_seconds=30, grep="NAV")
# Look for: "[smartMinimapClick] Verification failed (hover action: 'Cancel')"

# Workaround: Use shorter distances or retry
send_command("GOTO 3123 3102 0")  # Shorter distance more reliable
```

**Log pattern indicating failure:**
```
[smartMinimapClick] Bezier missed minimap (hover action: 'Cancel'), using movePrecisely
[smartMinimapClick] Verification failed (hover action: 'Cancel'), clicking anyway
Option: "Cancel" | Target: ""
```

### 4. Home Teleport Needs CAST_SPELL Command

**What happened:** Clicked Home Teleport widget (14286848) but nothing happened.
**Why:** Widget click selects spell but doesn't cast it (no target needed for Home Teleport, but still needs cast action).
**Solution:**
```python
# BAD - Widget click doesn't cast
click_widget(widget_id=14286848)  # Selects but doesn't cast

# GOOD - Use CAST_SPELL command
send_command("CAST_SPELL Home_Teleport")  # Actually casts the spell
```

### 5. Multiple Clients Cause Display Conflicts

**What happened:** Screenshots returned black. Two RuneLite clients running on display :2.
**Why:** Window capture gets confused with multiple windows.
**Solution:**
```python
# Check for multiple clients
runelite_status(list_all=True)
# Returns: {"instances": [{"account_id": "superape"}, {"account_id": "main"}]}

# Kill specific client by account, not pkill
stop_runelite(account_id="main")  # Safe - only stops one client

# NEVER use pkill - kills all clients
# Bash("pkill -f runelite")  # DANGEROUS
```

### 6. click_continue vs click_text("continue")

**What happened:** `click_continue()` returned "No continue button visible" but dialogue was open.
**Why:** `click_continue` looks for specific widget structure. Some dialogues have different layouts.
**Solution:**
```python
# Try click_continue first (faster)
result = click_continue()
if not result["success"]:
    # Fallback to text search
    click_text("continue")
    # Or try with full text
    click_text("Click here to continue")
```

### 7. INTERACT_NPC Works, CLICK_NPC in Spell Mode Doesn't

**What happened:** After selecting Wind Strike spell, CLICK_NPC Chicken clicked "Cancel".
**Why:** In spell targeting mode, the action changes from "Attack" to "Cast Wind Strike". CLICK_NPC doesn't verify the action.
**Solution:**
```python
# For spells, use CAST_SPELL_NPC (handles everything)
send_command("CAST_SPELL_NPC Wind_Strike Chicken")

# Or manual two-step:
click_widget(widget_id=14286856)  # Wind Strike widget
send_command("INTERACT_NPC Chicken Attack")  # INTERACT verifies menu action
```

## Anti-Patterns

1. **Don't** use `pkill -f runelite` - Kills ALL clients including ones you want running
2. **Don't** cast spells from far away - Walk within ~5 tiles first
3. **Don't** click doors without positioning - Multiple doors cause wrong selection
4. **Don't** assume widget click = spell cast - Some spells need CAST_SPELL command
5. **Don't** ignore "Cancel" in logs - Indicates mouse missed target

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="NAV")` | Check GOTO/navigation failures |
| `get_logs(grep="CAST")` | Check spell casting issues |
| `tail -20 /tmp/runelite_<account>.log` | Raw logs when MCP logs empty |
| `runelite_status(list_all=True)` | Find duplicate clients |
| `query_nearby(name_filter="Chicken")` | Check NPC distances |
| `get_transitions()` | Find doors/stairs with state |

## Interface Gaps Identified

- [ ] **Plugin needs:** CAST_SPELL_NPC should walk closer automatically if bounds are off-screen
- [ ] **Plugin needs:** Log NPC bounds when CAST_SPELL_NPC fails for debugging
- [ ] **MCP needs:** Screenshot tool should handle multiple windows gracefully
- [ ] **MCP needs:** GOTO should retry with shorter hops on minimap click failure
- [ ] **CLAUDE.md needs:** Document that Home Teleport requires CAST_SPELL not widget click

## Files Modified

| File | Change |
|------|--------|
| `routines/tutorial_island/09_banking.yaml` | Added exit_door_position, split step 9 into GOTO+Door |
| `routines/tutorial_island/10_prayer_magic.yaml` | Added step 29 Home Teleport, updated pitfalls 6-11 |

## Summary Statistics

- **Total time:** ~45 minutes for sections 9-10
- **Major blockers:** CAST_SPELL_NPC bounds (15 min), GOTO failures (10 min), Home Teleport (5 min)
- **Successful patterns identified:** 7
- **YAML improvements made:** 2 files updated with lessons
