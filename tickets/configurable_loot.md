# Configurable Loot System

## Status: IMPLEMENTED

## Problem

Loot items are hardcoded in `PlayerHelpers.java:17843`:
```java
String[] valuableLoot = {"Law rune", "Nature rune", "Fire rune", "Water rune"};
```

Every loot change requires:
1. Edit Java source
2. Rebuild plugin (35+ seconds)
3. Restart RuneLite

## Proposed Solutions

### Option A: Command Arguments (Simplest)

Pass loot items directly in KILL_LOOP command:

```
KILL_LOOP Hill_Giant 500 loot:Law_rune,Fire_rune,Water_rune,Big_bones
```

**Pros:**
- No config files needed
- Flexible per-session
- Easy to implement

**Cons:**
- Long command strings
- Can't save presets

### Option B: YAML Routine Config (Recommended)

Define loot in routine YAML files:

```yaml
# routines/combat/hill_giants.yaml
name: "Hill Giants Combat"
npc: "Hill Giant"
kills: 500

loot:
  priority:
    - "Law rune"
    - "Nature rune"
    - "Fire rune"
    - "Water rune"
  bones:
    - "Big bones"
  ignore:
    - "Limpwurt root"
    - "Beer"

eating:
  threshold_percent: 50
  food: "Swordfish"
```

Then run with:
```
COMBAT_ROUTINE routines/combat/hill_giants.yaml
```

**Pros:**
- Reusable presets
- Full combat config in one place
- Version controlled
- No plugin rebuild needed

**Cons:**
- New command needed
- More complex implementation

### Option C: External Config File

Single `~/.manny/loot_config.yaml` read at runtime:

```yaml
default_loot:
  - "Law rune"
  - "Nature rune"
  - "Coins"

profiles:
  hill_giants:
    - "Law rune"
    - "Fire rune"
    - "Big bones"

  lesser_demons:
    - "Rune med helm"
    - "Fire rune"
```

**Pros:**
- Change without restart (if watched)
- Central config

**Cons:**
- Another file to manage
- Profile selection mechanism needed

## Recommended Approach

**Phase 1: Command Arguments** (Quick win)
- Add optional `loot:item1,item2` parameter to KILL_LOOP
- Falls back to default if not specified
- 1-2 hour implementation

**Phase 2: Routine YAML** (Full solution)
- Create COMBAT_ROUTINE command
- Read full config from YAML
- Includes loot, eating, escape conditions
- 4-6 hour implementation

## Implementation Notes

### Phase 1 Changes

In `handleKillLoop()`:
```java
// Parse: KILL_LOOP Hill_Giant 500 loot:Law_rune,Fire_rune
String[] lootItems = defaultLoot;
if (args.contains("loot:")) {
    String lootArg = extractArg(args, "loot:");
    lootItems = lootArg.replace("_", " ").split(",");
}
```

### Phase 2 Changes

1. Create `CombatRoutineConfig` class to parse YAML
2. Add `COMBAT_ROUTINE <path>` command
3. Pass config to existing KILL_LOOP logic
4. Add MCP tool `execute_combat_routine(path)`

## Implementation Complete

### What Was Built

1. **MCP Tool** (`mcptools/tools/commands.py`):
   - `execute_combat_routine(routine_path, kills?, account_id?)`
   - Reads YAML, writes JSON to `/tmp/manny_combat_config.json`
   - Sends `KILL_LOOP_CONFIG <path>` to Java

2. **Java Handler** (`PlayerHelpers.java`):
   - `handleKillLoopConfig(configPath)` reads JSON config
   - Stores in `activeCombatConfig` class field
   - Calls existing `handleKillLoop` with parsed params

3. **Loot Section Modified**:
   - Checks `activeCombatConfig.lootItems` if available
   - Falls back to default loot list otherwise

4. **Example Routine** (`routines/combat/hill_giants.yaml`):
   ```yaml
   name: "Hill Giants"
   npc: "Hill Giant"
   kills: 500
   loot:
     items: ["Law rune", "Fire rune", "Water rune"]
     bones: ["Big bones"]
     ignore: ["Limpwurt root"]
   ```

### Usage

```python
# Via MCP
execute_combat_routine("routines/combat/hill_giants.yaml")

# With kill count override
execute_combat_routine("routines/combat/hill_giants.yaml", kills=100)
```

### Requires Restart

Changes require RuneLite restart to take effect.

## Related Files

- `manny_src/utility/PlayerHelpers.java` - KILL_LOOP_CONFIG handler (line ~18006)
- `mcptools/tools/commands.py` - execute_combat_routine MCP tool
- `routines/combat/hill_giants.yaml` - Example routine
