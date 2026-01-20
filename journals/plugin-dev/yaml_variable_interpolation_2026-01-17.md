# YAML Variable Interpolation - Design & Usage
**Date:** 2026-01-17

## The Problem

Switching a routine between different items (e.g., tuna vs swordfish) required editing 4-5 places manually. The `config` section existed but was purely documentation - values weren't actually used anywhere.

## Solution

Added `${variable}` interpolation to the routine executor. Variables defined in `config` are substituted into `args`, `await_condition`, and `stop_conditions` at runtime.

## Key Lessons

### 1. Underscore Filter for Command Args

**What happened:** Item names have two forms - commands need underscores, conditions need spaces.
**Why:** Plugin command parser splits on spaces. `BANK_WITHDRAW Raw swordfish 28` parses as 4 args, not 3.
**Solution:**
```yaml
config:
  raw_food: "Raw swordfish"  # Store with spaces (human-readable)

steps:
  # BAD - spaces in command args break parsing
  args: "${raw_food} 28"  # -> "Raw swordfish 28" (parsed wrong)

  # GOOD - |underscore filter for command args
  args: "${raw_food|underscore} 28"  # -> "Raw_swordfish 28" (correct)
  await_condition: "has_item:${raw_food}"  # -> "has_item:Raw swordfish" (spaces OK here)
```

### 2. Regex Pattern for Variable Matching

**Pattern:** `\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\|([a-zA-Z_]+))?\}`

Matches:
- `${variable}` - Simple substitution
- `${variable|filter}` - With filter

Undefined variables are left as-is (no error) to allow partial migrations.

## Usage Pattern

```yaml
# Define once in config
config:
  raw_food: "Raw swordfish"
  quantity: 28

# Use everywhere with ${variable}
steps:
  - action: BANK_WITHDRAW
    args: "${raw_food|underscore} ${quantity}"
    await_condition: "has_item:${raw_food}"

  - action: WAIT
    await_condition: "no_item:${raw_food}"

loop:
  stop_conditions:
    - "no_item_in_bank:${raw_food}"
```

**To change fish type:** Edit `raw_food: "Raw tuna"` in config - all references update automatically.

## Files Modified

| File | Change |
|------|--------|
| `mcptools/tools/routine.py` | Added `interpolate_variables()` function (~40 lines) |
| `routines/skilling/cooking_lumbridge.yaml` | Updated to use `${raw_food}` variables |
| `tickets/yaml_routine_variables.md` | Marked as implemented |

## Future Extensions

Could add more filters if needed:
- `${variable|lowercase}` - Force lowercase
- `${variable|uppercase}` - Force uppercase
- `${variable|capitalize}` - Title case
