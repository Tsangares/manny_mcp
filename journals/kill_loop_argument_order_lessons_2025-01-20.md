# KILL_LOOP Argument Order - Lessons Learned
**Date:** 2025-01-20

## The Problem

KILL_LOOP was stopping after approximately 100 kills despite expecting it to run much longer. The command `KILL_LOOP Giant_frogs 500` appeared to ignore the "500" limit.

## Root Cause

The command format requires a **food argument** before the kill count:

```
KILL_LOOP <npc_name> <food_name> [max_kills] [area_bounds]
```

When calling `KILL_LOOP Giant_frogs 500`:
- `parts[1]` = "Giant_frogs" → NPC name ✓
- `parts[2]` = "500" → **Parsed as food name** ❌
- `parts[3]` = missing → **max_kills defaults to 100** ❌

**Code reference:** `manny_src/utility/PlayerHelpers.java:17431`
```java
int maxKills = parts.length > 2 ? Integer.parseInt(parts[2]) : 100;
```

The "500" was being interpreted as a food item name, and since no food called "500" exists, the loop would stop early due to HP safety checks when it couldn't find food to eat.

## Key Lessons

### 1. Food Argument is Mandatory (Position 2)

**What happened:** Kill count was misinterpreted as food name
**Why:** Positional argument parsing - no keyword arguments

**Solution:**
```python
# BAD - "500" becomes food name, max_kills defaults to 100
send_command("KILL_LOOP Giant_frogs 500")

# GOOD - explicit food argument, then kill count
send_command("KILL_LOOP Giant_frogs none 500")      # No food management
send_command("KILL_LOOP Giant_frogs Trout 500")     # Use Trout for healing
send_command("KILL_LOOP Giant_frogs Cooked_meat 500")  # Use cooked meat
```

### 2. Use "none" to Disable Food Management

**What happened:** Without valid food, HP safety checks trigger early stops
**Why:** Code checks HP and breaks loop if food management enabled but no food found

**Safety stops triggered by invalid food:**
- HP < 60% with empty inventory → "out of food" error (line 17569)
- HP < 30% → "critical HP" safety stop (line 17575)
- HP ≤ 50% with food disabled → graceful stop (line 17588)

**Solution:**
```python
# If you don't need healing (high defense, prayer, etc.)
send_command("KILL_LOOP Giant_frogs none 1000")

# If you need healing
send_command("KILL_LOOP Giant_frogs Lobster 1000")
```

## Anti-Patterns

1. **Don't** omit the food argument - kill count will be misinterpreted as food name
2. **Don't** assume positional arguments are optional in the middle - only trailing arguments can be omitted

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="KILL_LOOP")` | See how arguments were parsed |
| `get_command_examples(command="KILL_LOOP")` | Verify correct format |
| `find_command(command="KILL_LOOP")` | Read handler source code |

## Interface Gaps Identified

- [ ] CLAUDE.md needs: Document KILL_LOOP argument order explicitly
- [ ] MCP could add: Validation warning when kill count looks like a number in food position
- [ ] Consider: Named arguments would prevent this class of errors entirely

## Command Reference

```
KILL_LOOP <npc_name> <food_name> [max_kills] [area_bounds]

Arguments:
  npc_name   - Target NPC (use underscores: Giant_frogs)
  food_name  - Food item OR "none" to disable food management
  max_kills  - Optional, defaults to 100
  area_bounds - Optional, format: x1,y1,x2,y2

Examples:
  KILL_LOOP Cow none 500
  KILL_LOOP Giant_frog Trout 200
  KILL_LOOP Hill_Giant Lobster 100 3095,9825,3125,9855
```
