# Aux Account (LOSTimposter) Leveling Plan

**Account Status:** Fresh from Tutorial Island
**Goal:** Build a functional auxillary bot
**Strategy:** Routine-based automation for token efficiency

## Current Stats
- Combat: Level 3
- All skills: Level 1
- Gold: 0
- Location: Lumbridge

## Phase 1: Early Combat (Target: Combat 15)

**Routine:** `routines/combat/chicken_killer_training.yaml`

```bash
execute_routine(routine_path="routines/combat/chicken_killer_training.yaml")
```

**Why chickens first:**
- Level 1 NPCs = zero risk even at combat 3
- Feathers drop (~45gp/kill) for early gold
- Raw chicken for cooking practice or selling
- Right next to Lumbridge spawn

**Expected outcome:**
- Combat level 10-15
- ~3,000 feathers (~9,000gp)
- Ready for cows

## Phase 2: Intermediate Combat (Target: Combat 30)

**Routine:** `routines/combat/cow_killer_training.yaml`

After combat 15:
```bash
execute_routine(routine_path="routines/combat/cow_killer_training.yaml")
```

**Why cows:**
- Level 2 NPCs - safe at combat 15+
- Cowhide drops (~150gp each) - best early F2P money
- Near Lumbridge bank for easy banking

**Expected outcome:**
- Combat level 25-30
- Bank full of cowhides (~50k gp potential)

## Phase 3: Fishing Foundation (Target: Fishing 40)

**Routine:** `routines/skilling/fishing_draynor.yaml`

```bash
execute_routine(routine_path="routines/skilling/fishing_draynor.yaml")
```

**Why fishing:**
- AFK-able skill
- Fish = free food for combat
- Fishing 40 unlocks lobsters at Karamja

## Phase 4: Easy Quests (Target: 10+ QP)

Run quest routines for XP rewards:

| Quest | Routine | Rewards |
|-------|---------|---------|
| Cook's Assistant | `routines/quests/cooks_assistant.yaml` | 300 Cooking XP |
| Sheep Shearer | `routines/quests/sheep_shearer.yaml` | 150 Crafting XP, 60gp |
| Restless Ghost | `routines/quests/restless_ghost.yaml` | 1,125 Prayer XP |

## Phase 5: Money Making Loop

Once combat 30+ and fishing 40:

**Karamja Lobsters** - `routines/skilling/fishing_karamja_lobster.yaml`
- ~30k gp/hour from lobsters
- Can cook for Cooking XP too

**Cow Hides** - `routines/combat/cow_killer_training.yaml` (KILL_COW_GET_HIDES mode)
- Combat XP + 150gp per hide
- ~20k gp/hour

## Routine Execution Order

1. `chicken_killer_training.yaml` - Until combat 15
2. `cow_killer_training.yaml` - Until combat 25
3. `fishing_draynor.yaml` - Until fishing 20
4. `cooks_assistant.yaml` - Quest
5. `sheep_shearer.yaml` - Quest
6. `cow_killer_training.yaml` - Until combat 30
7. `fishing_draynor.yaml` - Until fishing 40
8. Loop: Karamja lobsters or cow hides

## Session Monitoring

Check progress periodically:
```python
get_game_state(account_id="aux", fields=["skills", "inventory"])
```

Restart if stuck:
```python
check_health(account_id="aux")
restart_if_frozen(account_id="aux")
```
