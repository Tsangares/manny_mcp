# USE_ITEM_ON_OBJECT/NPC Argument Parsing - Lessons Learned
**Date:** 2025-01-16

## The Problem

Commands like `USE_ITEM_ON_OBJECT Ghost's skull Coffin` silently failed. The command appeared to dispatch successfully (`{"dispatched": true}`) but nothing happened in-game.

## Root Cause

The switch statement in `PlayerHelpers.java:10005` only passed `parts[1]` to the handler:

```java
case "USE_ITEM_ON_OBJECT":
    return handleUseItemOnObject(parts.length > 1 ? parts[1] : "");
```

When the command `USE_ITEM_ON_OBJECT Ghost's skull Coffin` was split on spaces:
- `parts[0]` = "USE_ITEM_ON_OBJECT"
- `parts[1]` = "Ghost's"  ← Only this was passed!
- `parts[2]` = "skull"
- `parts[3]` = "Coffin"

The handler at line 14397 received only "Ghost's" and couldn't find a space to split item/object names.

## Key Lessons

### 1. Switch Statement Argument Passing is Inconsistent

**What happened:** Some commands correctly join all remaining args, others only pass `parts[1]`.

**Why:** Copy-paste errors. Simple single-arg commands use `parts[1]`, but multi-word commands need the full args.

**Solution:**
```java
// BAD - only works for single-word arguments
return handleUseItemOnObject(parts.length > 1 ? parts[1] : "");

// GOOD - preserves multi-word arguments
return handleUseItemOnObject(parts.length > 1 ? String.join(" ", Arrays.copyOfRange(parts, 1, parts.length)) : "");
```

### 2. The Handler Logic Was Correct

The handler used `args.lastIndexOf(' ')` to split - correctly assuming object names are single words while item names can be multi-word ("Ghost's skull" + "Coffin"). The bug was upstream in the switch statement.

### 3. Silent Failures are Dangerous

The command dispatched successfully but the handler silently failed because it couldn't parse the truncated args. No error was logged because the `lastIndexOf(' ')` check returned -1, causing an early return with a generic error.

## Anti-Patterns

1. **Don't assume `parts[1]` is sufficient** - Any command that takes `<item_name> <target>` format needs full args
2. **Don't trust dispatch success** - `{"dispatched": true}` only means the command was written to the file, not that it executed correctly

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="USE_ITEM")` | See what the handler actually received |
| `get_command_examples(command="USE_ITEM_ON_OBJECT")` | Verify expected format |
| `find_command(command="USE_ITEM_ON_OBJECT")` | Find switch case and handler |

## Interface Gaps Identified

- [x] Plugin fix: Both `USE_ITEM_ON_OBJECT` and `USE_ITEM_ON_NPC` switch cases now use `String.join()` pattern

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/PlayerHelpers.java:10005` | USE_ITEM_ON_OBJECT: `parts[1]` → `String.join(" ", Arrays.copyOfRange(parts, 1, parts.length))` |
| `manny_src/utility/PlayerHelpers.java:10008` | USE_ITEM_ON_NPC: Same fix |

## Pattern Reference

Commands that need full args (multi-word support):
```java
// These use String.join pattern (GOOD):
FIND_OBJECT, WIKI_QUERY, USE_ITEM_ON_OBJECT, USE_ITEM_ON_NPC

// These use parts[1] (only for single-word args):
BANK_OPEN, QUERY_NPCS, FIND_NPC
```

When adding new commands that accept `<item_name>` or `<object_name>`, always use the `String.join()` pattern.
