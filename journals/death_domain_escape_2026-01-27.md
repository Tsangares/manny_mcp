# Death's Domain Escape - Lessons Learned
**Date:** 2026-01-27

## The Problem

After first death, player is teleported to Death's Domain (coordinates ~10700, 1030). The exit portal is blocked by Death who requires completing a mandatory tutorial dialogue. `CLICK_CONTINUE` command fails repeatedly, trapping the player in an infinite dialogue loop.

## Root Cause

1. **CLICK_CONTINUE doesn't work** - The Death tutorial uses a special dialogue widget (ID 12648448) that isn't detected by the standard `click_continue()` MCP tool
2. **Tutorial is mandatory** - Death blocks portal exit with "I haven't finished talking to you yet" until ALL dialogue topics are completed
3. **Early exit blocked** - Selecting "I think I'm done here" before completing all topics triggers a rejection message

## Key Lessons

### 1. Use Space Key Instead of CLICK_CONTINUE

**What happened:** `CLICK_CONTINUE` and `click_continue()` MCP tool returned success but dialogue didn't advance.
**Why:** Special tutorial widget not in standard dialogue widget groups.
**Solution:**
```python
# BAD - Doesn't work in Death's Domain
send_command("CLICK_CONTINUE")  # Returns success but no effect
click_continue()  # Same issue

# GOOD - Space key works
send_input(input_type="key", key="Space")  # Actually advances dialogue
```

### 2. Must Complete ALL Dialogue Topics

**What happened:** Selecting "I think I'm done here" triggered "more topics to cover" message.
**Why:** Death requires covering all 3 mandatory topics before allowing exit.
**Solution:**
```python
# Must select each topic in order:
click_text("How do I pay a gravestone fee")  # Topic 1
# Space through explanation...
click_text("long do I have to return")       # Topic 2 (partial match)
# Space through explanation...
click_text("I know what will happen")        # Topic 3 (partial match)
# Space through explanation...
click_text("I think I'm done here")          # NOW this works
```

### 3. Talk-to Death, Not Collect

**What happened:** `INTERACT_NPC Death Collect` triggered "Perhaps we should just talk instead" loop.
**Why:** Collect action requires completed tutorial; Talk-to starts the tutorial.
**Solution:**
```python
# BAD - Triggers rejection loop
send_command("INTERACT_NPC Death Collect")

# GOOD - Starts proper tutorial
send_command("INTERACT_NPC Death Talk-to")
```

### 4. Detect Death's Domain by Coordinates

**What happened:** Standard game state showed x: 10698, y: 1032 - far outside normal world bounds.
**Why:** Death's Domain is an instanced area with abnormal coordinates (x > 10000).
**Solution:**
```python
state = get_game_state()
if state["location"]["x"] > 10000:
    # Player is in Death's Domain - trigger escape routine
    pass
```

## Anti-Patterns

1. **Don't spam CLICK_CONTINUE** - Wastes 20+ tool calls with no progress
2. **Don't try portal before tutorial complete** - Death intercepts every attempt
3. **Don't use Collect action** - Triggers endless "talk instead" loop
4. **Don't skip dialogue topics** - Death remembers what you haven't asked

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_game_state(fields=["location"])` | Check if x > 10000 (Death's Domain) |
| `query_nearby(name_filter="Death")` | Find Death NPC for interaction |
| `scan_tile_objects("portal")` | Find exit portal |
| `find_widget(text="continue")` | Find dialogue continue widget |
| `send_input(input_type="key", key="Space")` | Advance dialogue reliably |

## Interface Gaps Identified

- [x] **Routine created:** `routines/utility/death_escape.yaml`
- [ ] **Plugin could add:** Detect Death's Domain state automatically
- [ ] **MCP could add:** Auto-detect failed dialogue and suggest Space key

## Files Modified

| File | Change |
|------|--------|
| `routines/utility/death_escape.yaml` | New routine for escaping Death's Domain |
| `journals/death_domain_escape_2026-01-27.md` | This journal |

## Time Lost

**~25 minutes** stuck in dialogue loop before discovering Space key workaround.

## Critical Takeaway

**When CLICK_CONTINUE fails repeatedly, try `send_input(input_type="key", key="Space")`** - it uses Java AWT key events which work in special dialogue widgets where the normal continue command fails.
