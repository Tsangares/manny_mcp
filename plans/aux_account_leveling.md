# Aux Account (LOSTimposter) Leveling Plan

**Last Updated:** 2026-01-19
**Account Status:** Combat training at Giant Frogs
**Goal:** Build a functional auxiliary bot with 40 combat stats

## Current Stats (2026-01-19)

| Skill | Level | XP | Target | Progress |
|-------|-------|-----|--------|----------|
| Attack | 34 | 21,396 | 40 | 57% |
| Strength | 38 | 31,608 | 40 | 85% |
| Defence | 20 | 4,548 | 40 | 12% |
| Hitpoints | 33 | 20,128 | 40 | 54% |
| Prayer | 23 | 7,014 | 25 | 56% |
| Magic | 1 | 69 | - | - |
| Ranged | 1 | 76 | - | - |

**Combat Level:** ~42
**Gold:** ~50k (from cowhides sold earlier)
**Location:** Lumbridge Swamp (Giant Frogs)

## Training History

### Phase 1: Chickens (COMPLETED)
- Combat 3 → 10
- Collected feathers

### Phase 2: Cows (COMPLETED)
- Combat 10 → 20
- Banked cowhides for gold

### Phase 3: Giant Frogs (IN PROGRESS)
**Current training spot.** Better than Al Kharid Warriors because:
- Big Bones drops → Prayer XP (currently 23!)
- Lower HP = faster kills
- Less damage taken

**Command:** `KILL_LOOP Giant_frog 1000`

**Target:** 40 Attack before moving on

## Next Steps

### Immediate (After 40 Attack)
1. **Switch to Strength training** - Change combat style
2. **Continue at frogs** until 40 Strength (already 38, almost done)
3. **Then Defence** - Train to 40

### After 40/40/40 Base Stats
- Move to **Hill Giants** for better XP and Big Bones
- Or **Flesh Crawlers** in Stronghold for herbs + combat XP
- Consider **Restless Ghost** quest for prayer XP boost

### Quests to Complete
| Quest | Status | Rewards |
|-------|--------|---------|
| Cook's Assistant | NOT STARTED | 300 Cooking XP |
| Sheep Shearer | NOT STARTED | 150 Crafting XP |
| Restless Ghost | NOT STARTED | 1,125 Prayer XP |
| Imp Catcher | NOT STARTED | 875 Magic XP |

## Inventory Setup for Frogs

- 4-5 cowhides (to sell/bank later)
- 15-20 Tuna for food
- Big Bones to bury (auto-picked up by loop)

## Session Notes

### 2026-01-19 Session
- Started at Attack 24, now at 34
- HP leveled from 31 → 33
- Prayer leveled from 21 → 23
- XP rate: ~7-9k Attack XP/hour
- ETA to 40 Attack: ~2 hours

### Known Issues
- Kill loop sometimes stops (needs restart every ~30-60 min)
- Disconnects require manual restart
- Giant frogs may not be nearby (check with `query_nearby`)

## Monitoring Commands

```python
# Check current stats
get_game_state(account_id="aux", fields=["skills", "health", "inventory"])

# Restart kill loop
send_command(account_id="aux", command="KILL_LOOP Giant_frog 1000")

# Check health
check_health(account_id="aux")

# If frozen/DC
restart_if_frozen(account_id="aux")
start_runelite(account_id="aux")
```

## Long-Term Goals

1. **40/40/40 melee stats** - Base for most F2P content
2. **43 Prayer** - Protect from Melee
3. **50 Magic** - Unlock High Alchemy
4. **40 Fishing** - Lobsters at Karamja
5. **Complete F2P quests** - Quest cape potential
