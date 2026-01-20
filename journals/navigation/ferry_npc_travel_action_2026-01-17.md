# Ferry NPC Travel Action - Lessons Learned
**Date:** 2026-01-17

## The Problem

During Karamja fishing automation, each ferry trip (Port Sarim ↔ Karamja) required 8+ dialogue clicks, consuming ~20 tool calls per round trip. The routine should have taken 2 tool calls per trip.

## Root Cause

Used `INTERACT_NPC Captain_Tobias Talk-to` instead of `INTERACT_NPC Captain_Tobias Travel`. The `Talk-to` action opens full dialogue requiring:
1. Click continue (NPC greeting)
2. Select "Yes please" option
3. Click continue (fare confirmation)
4. Wait for travel animation

The `Travel` action right-clicks and selects Travel directly from the context menu, skipping ALL dialogue.

## Key Lessons

### 1. Use Travel Action for Ferry NPCs

**What happened:** Manually navigated 8+ dialogue screens per ferry trip, wasting tool calls.
**Why:** Assumed Talk-to was the only way to travel. Didn't check the routine file or test right-click menu.

**Solution:**
```python
# BAD - Opens dialogue, requires 8+ clicks
send_command("INTERACT_NPC Captain_Tobias Talk-to")
click_continue()  # Greeting
click_text("Yes please")  # Option
click_continue()  # Confirmation
# ... more clicks

# GOOD - Right-click menu, skips all dialogue
send_command("INTERACT_NPC Captain_Tobias Travel")  # Port Sarim → Karamja
send_command("INTERACT_NPC Customs_officer Travel")  # Karamja → Port Sarim
```

### 2. Check Existing Routines Before Manual Execution

**What happened:** Implemented manual fishing loop instead of using existing `fishing_karamja_harpoon.yaml` routine.
**Why:** Started with manual steps to debug, then never switched back to routine.

**Solution:**
```python
# BAD - Manual loop with 20+ tool calls per trip
send_command("FISH swordfish")
# ... wait ...
send_command("GOTO 2954 3147 0")
send_command("INTERACT_NPC Customs_officer Talk-to")
# ... 8 dialogue clicks ...

# GOOD - Use the existing routine
execute_routine(routine_path="routines/skilling/fishing_karamja_harpoon.yaml")
```

### 3. Right-Click Menu Actions Are Often Faster

**What happened:** Didn't consider right-click options for NPCs.
**Why:** Assumed NPCs with dialogue need Talk-to first.

**Pattern:** Many NPCs have shortcut actions in right-click menu:
- `Travel` - Skips travel dialogue
- `Trade` - Opens shop directly
- `Bank` - Opens bank interface directly

## Anti-Patterns

1. **Don't** use `Talk-to` for utility NPCs - Check right-click menu for direct actions first
2. **Don't** implement manual loops when routines exist - Check `routines/` directory first
3. **Don't** assume dialogue is required - Many interactions have shortcut actions

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `query_nearby(name_filter="Captain")` | See NPC and available actions |
| `get_command_examples(command="INTERACT_NPC")` | See how routines use the command |

## Interface Gaps Identified

None - the functionality exists, I just didn't use it correctly.

- [x] Routine exists: `routines/skilling/fishing_karamja_harpoon.yaml`
- [x] CLAUDE.md documents `Travel` action in Port Sarim/Karamja section
- [ ] CLAUDE.md could emphasize: "Check right-click menu for NPC shortcut actions"

## Time Wasted

~30 minutes of inefficient dialogue navigation before user pointed out the `Travel` action. Each trip took 20+ tool calls instead of 2.

## Related Files

| File | Relevant Content |
|------|------------------|
| `routines/skilling/fishing_karamja_harpoon.yaml:69` | `args: "Captain_Tobias Travel"` |
| `routines/skilling/fishing_karamja_harpoon.yaml:131` | `args: "Customs_officer Travel"` |
| `CLAUDE.md` | Port Sarim/Karamja Travel section documents correct usage |
