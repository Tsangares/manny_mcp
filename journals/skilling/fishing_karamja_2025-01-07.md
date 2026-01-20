# Fishing at Karamja - Session Pitfalls
**Date:** 2025-01-07

## Session Goal
Fish lobsters at Musa Point (Karamja) and create an automated routine to catch 1000 lobsters.

## The Journey

Started at Port Sarim with 990 coins. Goal was to:
1. Buy lobster pot from Gerrant's fishing shop
2. Take boat to Musa Point
3. Fish lobsters

## Pitfalls Encountered

### 1. RuneLite Not Managed by MCP Server

**Problem:** Commands sent via `send_command()` were not being executed. The command file was written but nothing happened in-game.

**Root Cause:** RuneLite was running, but NOT started through the MCP server. The MCP server tracks a `managed_process` - if RuneLite was started manually or from a previous session, the MCP server doesn't control it and can't verify command execution.

**Solution:** Always use `start_runelite()` MCP tool to ensure the process is managed:
```python
# Check first
runelite_status()  # Shows managed: false

# Restart through MCP
start_runelite()   # Kills existing, starts managed process
```

**Lesson:** If commands aren't executing, check `runelite_status()` for `managed: true`.

### 2. NPC Interaction Parsing - Spaces vs Underscores

**Problem:** `INTERACT_NPC Captain Tobias Pay-fare` failed. Plugin parsed it as:
- NPC name: "Captain"
- Action: "Tobias Pay-fare"

**Root Cause:** The command parser splits on spaces. Multi-word NPC names must use underscores.

**Solution:**
```python
# BAD
INTERACT_NPC Captain Tobias Pay-fare

# GOOD
INTERACT_NPC Captain_Tobias Pay-fare
```

**Lesson:** Always use underscores for multi-word NPC/object names: `Captain_Tobias`, `Fishing_spot`, `Large_door`

### 3. Discovering Available Actions

**Problem:** `INTERACT_NPC Captain_Tobias Pay-fare` failed with "action not found". The action "Pay-fare" doesn't exist on Captain Tobias.

**Root Cause:** Assumed the action name without checking what actions were actually available.

**Solution:** Check logs after failed interaction to see available actions:
```
Menu option not found: option='Pay-fare', target='Captain Tobias'
Available menu entries:
- Travel      <-- This is what we need!
- Talk-to
- Examine
```

**Correct command:** `INTERACT_NPC Captain_Tobias Travel`

**Lesson:** When an action fails, always check `get_logs()` - it shows available actions for the NPC.

### 4. Plugin Freeze - State File Staleness

**Problem:** GOTO commands were timing out. Player wasn't moving despite commands being sent.

**Diagnosis:** `check_health()` showed state file was 213 seconds stale - the plugin had frozen.

**Root Cause:** Unknown. Possibly thread contention or the plugin hitting an edge case.

**Solution:** Restart RuneLite when state file becomes stale:
```python
health = check_health()
if health["state_file"]["age_seconds"] > 30:
    start_runelite()  # Restart
```

**Lesson:** Monitor state file freshness. Staleness > 30 seconds indicates plugin freeze.

### 5. FISH Command Clicking Wrong Fishing Spots

**The Big One.** This consumed most of the debugging time.

**Problem:** `FISH lobster` command kept clicking on the wrong fishing spots. Lobster requires "Cage" action, but the plugin clicked on "Small Net" spots instead.

**Root Cause:** At Musa Point, there are two types of fishing spots with the SAME NAME ("Fishing spot"):
- ID 1521: Has "Small Net" and "Bait" actions (for shrimp, anchovies)
- ID 1522: Has "Cage" and "Harpoon" actions (for lobster, tuna)

The plugin's `interactWithNPC()` finds the **nearest** NPC by name. Since both types are named "Fishing spot", it finds whichever is closest - often the wrong one.

```
[FISH] Cage on Fishing spot
[InteractionSystem] Menu option not found: option='Cage', target='Fishing spot'
Available menu entries:
- Bait
- Small Net      <-- Wrong spot type!
- Examine
```

**Attempted Solutions:**
1. Walking closer to Cage spots - still clicked wrong spots due to tie-breaking
2. Direct screen clicks via `send_input()` - hard to target correct spot visually
3. None fully worked within current plugin capabilities

**Correct Solution (requires plugin changes):**
The FISH command or INTERACT_NPC needs to filter by NPC ID, not just name:
```java
// Instead of:
NPC spot = getNPC("Fishing spot");  // Gets nearest by name

// Should be:
NPC spot = getNPC("Fishing spot", npcId=1522);  // Filter by ID
```

**Lesson:** When multiple NPCs share the same name but have different IDs/actions, the current "nearest by name" approach fails. Need ID-based filtering.

### 6. Level Requirement Not Met

**Problem:** After all the above, discovered lobster fishing requires level 40. Player was level 39.

**Solution:** Fish shrimp first to gain that last level. But this requires a small fishing net...

### 7. Missing Equipment

**Problem:** To fish shrimp (to level up), need a small fishing net. Inventory only had:
- Coins
- Fly fishing rod
- Harpoon
- Lobster pot

**Solution:** Need to return to Port Sarim to buy a small fishing net from Gerrant.

## Commands Reference

| Command | Notes |
|---------|-------|
| `INTERACT_NPC <name> <action>` | Use underscores for multi-word names |
| `FISH <fishType>` | Broken for Cage fishing spots (ID conflict) |
| `GOTO x y plane` | Can timeout; monitor state file freshness |
| `check_health()` | Essential for detecting plugin freezes |

## Fishing Spot IDs at Musa Point

| NPC ID | Actions | Fish Types |
|--------|---------|------------|
| 1521 | Small Net, Bait | Shrimp, Anchovies, Sardine, Herring |
| 1522 | Cage, Harpoon | Lobster, Tuna, Swordfish |

## Anti-Patterns

```python
# BAD: Assuming RuneLite is managed
send_command("FISH lobster")  # Might not work if not managed

# BAD: Spaces in NPC names
INTERACT_NPC Captain Tobias Travel

# BAD: Assuming action names
INTERACT_NPC Banker Bank  # Check logs for actual action name

# BAD: Trusting FISH command for Cage spots
FISH lobster  # Will click on nearest "Fishing spot" - likely wrong type
```

## Correct Patterns

```python
# Always verify managed status first
status = runelite_status()
if not status["process"]["managed"]:
    start_runelite()

# Use underscores for multi-word names
INTERACT_NPC Captain_Tobias Travel

# Check logs after failures to discover correct actions
get_logs(level="WARN", since_seconds=30)

# For fishing spots, may need manual screen clicks until plugin is fixed
send_input(input_type="click", x=480, y=350, button=1)
```

## Plugin Improvements Needed

1. **INTERACT_NPC_BY_ID** - New command to interact with NPC by ID, not just name
2. **FISH command enhancement** - Filter fishing spots by NPC ID based on fish type
3. **Better action discovery** - Tool to query available actions on nearest NPC before interacting

## Session Status
- Lobster pot: Purchased
- Boat to Karamja: Completed
- Lobster fishing: Blocked (wrong spot clicking + level 39)
- Next: Return to Port Sarim for small fishing net, fish shrimp to 40, retry lobsters

## Time Spent Debugging
- RuneLite not managed: 10 min
- NPC name parsing: 5 min
- Action discovery: 10 min
- Plugin freeze: 10 min
- Fishing spot ID issue: 45+ min (still unresolved in plugin)
- Level check: 2 min

**Total wasted time due to pitfalls: ~80 minutes**
