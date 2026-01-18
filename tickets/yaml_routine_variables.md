# Feature Request: YAML Routine Variables/Labels

**Date:** 2026-01-17
**Component:** Routine Executor
**Priority:** Medium
**Status:** ✅ Implemented

## Problem

Currently, when switching a routine between different items (e.g., tuna vs swordfish), you must manually edit multiple places in the YAML:

1. `config.raw_food` - documentation only, not actually used
2. Step 2 `args` - BANK_WITHDRAW command
3. Step 2 `await_condition` - has_item check
4. Step 10 `await_condition` - no_item check
5. `loop.stop_conditions` - bank empty check

This is error-prone and tedious. If you miss one, the routine breaks.

## Proposed Solution: Variable Interpolation

Allow the `config` section to define variables that get interpolated into step arguments and conditions.

### Syntax Option 1: `${variable}` interpolation

```yaml
config:
  raw_food: "Raw swordfish"
  cooked_food: "Swordfish"
  quantity: 28

steps:
  - id: 2
    action: BANK_WITHDRAW
    args: "${raw_food} ${quantity}"
    await_condition: "has_item:${raw_food}"

  - id: 10
    action: WAIT
    await_condition: "no_item:${raw_food}"

loop:
  stop_conditions:
    - "no_item_in_bank:${raw_food}"
```

### Syntax Option 2: Jinja2-style `{{ variable }}`

```yaml
config:
  raw_food: "Raw swordfish"

steps:
  - id: 2
    args: "{{ raw_food }} 28"
    await_condition: "has_item:{{ raw_food }}"
```

### Syntax Option 3: YAML anchors (native YAML)

```yaml
config:
  raw_food: &raw_food "Raw swordfish"
  raw_food_underscore: &raw_food_underscore "Raw_swordfish"

steps:
  - id: 2
    args: !join [*raw_food_underscore, " 28"]
    await_condition: !join ["has_item:", *raw_food]
```

## Implementation Notes

### In `execute_routine` (mcptools/tools/routine.py):

1. Parse `config` section at routine load time
2. Before executing each step, interpolate variables into:
   - `args`
   - `await_condition`
   - `description` (optional, for logging)
3. Also interpolate into `loop.stop_conditions`

### Underscore Handling

Item names have two forms:
- Command args use underscores: `Raw_swordfish`
- Conditions use spaces: `Raw swordfish`

Options:
1. Define both in config: `raw_food` and `raw_food_cmd`
2. Auto-convert: `${raw_food}` uses spaces, `${raw_food|underscore}` converts
3. Let the executor handle it based on context

## Benefits

1. **Single point of change** - Update config, routine works for different items
2. **Less error-prone** - No risk of missing a reference
3. **Reusable routines** - Same routine file works for multiple items
4. **Clearer intent** - Config section documents what's parameterized

## Example: Unified Cooking Routine

```yaml
name: "Lumbridge Cooking"
description: "Cook ${raw_food} at Lumbridge Castle range"

config:
  raw_food: "Raw swordfish"      # Change this one value
  cooked_food: "Swordfish"       # For documentation
  quantity: 28

steps:
  - id: 1
    action: BANK_OPEN

  - id: 2
    action: BANK_WITHDRAW
    args: "${raw_food|underscore} ${quantity}"
    await_condition: "has_item:${raw_food}"

  # ... cooking steps ...

  - id: 10
    action: WAIT
    await_condition: "no_item:${raw_food}"

loop:
  enabled: true
  repeat_from_step: 1
  stop_conditions:
    - "no_item_in_bank:${raw_food}"
```

## Alternative: Multiple Routine Files

Instead of variables, could have:
- `cooking_tuna.yaml`
- `cooking_swordfish.yaml`
- `cooking_lobster.yaml`

But this duplicates the entire routine and makes maintenance harder.

## Related

- Python's `string.Template` or `str.format()` could handle interpolation
- Jinja2 library if more complex templating needed
- YAML anchors are native but awkward for string concatenation

---

## Implementation (2026-01-17)

**Chosen syntax:** `${variable}` with `|underscore` filter

**Files modified:**
- `mcptools/tools/routine.py` - Added `interpolate_variables()` function
- `routines/skilling/cooking_lumbridge.yaml` - Updated to use variables

**Interpolation points:**
1. `args` field in steps
2. `await_condition` field in steps
3. `description` field in steps (for logging)
4. `stop_conditions` in loop config

**Filter support:**
- `${variable}` - Direct substitution
- `${variable|underscore}` - Replace spaces with underscores

**Example usage:**
```yaml
config:
  raw_food: "Raw swordfish"
  quantity: 28

steps:
  - action: BANK_WITHDRAW
    args: "${raw_food|underscore} ${quantity}"  # -> "Raw_swordfish 28"
    await_condition: "has_item:${raw_food}"      # -> "has_item:Raw swordfish"
```
