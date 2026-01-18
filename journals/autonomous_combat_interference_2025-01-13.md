# Autonomous Combat Interference in Multi-Combat Zones

**Date**: 2025-01-13
**Context**: KILL_LOOP with Al Kharid Warriors (multi-combat zone)
**Symptom**: Clicking confusion, camera jerking between targets

## Problem

When running `KILL_LOOP` in multi-combat zones, the autonomous combat system would interfere during gaps between kills, causing the plugin to click different targets than KILL_LOOP intended.

## Root Cause

Two issues combined:

### 1. Flag Timing Gap

The `manualCombatInProgress` flag only covered `attackNPC()` execution:

```java
// CombatSystem.java:663-673
public CombatResult attackNPC(...) {
    manualCombatInProgress = true;  // ON during attack
    try {
        return attackNPCInternal(...);
    } finally {
        manualCombatInProgress = false;  // OFF immediately after
    }
}
```

But KILL_LOOP has phases BETWEEN attacks where this flag is false:
- Looting drops
- Eating food
- Checking HP
- Finding next target

During these gaps, autonomous combat's `onGameTick()` would detect attackers and try to engage.

### 2. Arbitrary Attacker Selection

`getAttackerDirect()` returns the **first** NPC in iteration order:

```java
// CombatSystem.java:1698-1738
for (NPC npc : client.getTopLevelWorldView().npcs()) {
    if (npc.getInteracting() == player) {
        return npc;  // First one found - arbitrary!
    }
}
```

In multi-combat with 3-4 attackers, this is essentially random. KILL_LOOP uses LOS checks, distance sorting, and area bounds - they'd pick different targets.

### Timeline of Conflict

```
T=0: KILL_LOOP attacks Warrior_A (manualCombatInProgress=true)
T=1: Warrior_A dies (manualCombatInProgress=false)
T=2: KILL_LOOP looting... (flag still false!)
     GameTick fires
     Autonomous combat sees Warrior_B attacking
     Spawns executeFighting(Warrior_B)
T=3: KILL_LOOP finds Warrior_C, calls attackNPC(Warrior_C)
T=4: TWO threads clicking different targets
```

## Solution

Two-part fix:

### Part 1: Combat Command Flag

New flag that covers the ENTIRE command execution:

```java
// CombatSystem.java:60
private volatile boolean combatCommandActive = false;

// PlayerHelpers.java - handleKillLoop()
combatSystem.setCombatCommandActive(true);
try {
    // ... entire loop including loot/eat phases ...
} finally {
    combatSystem.setCombatCommandActive(false);
}
```

Checked in `onGameTick()` to fully suppress autonomous combat during KILL_LOOP.

### Part 2: Already-In-Combat Check

Prevents target switching even outside KILL_LOOP:

```java
// CombatSystem.java:1750-1772
private boolean isPlayerAlreadyInCombat() {
    Actor target = player.getInteracting();
    if (target instanceof NPC) {
        return !((NPC) target).isDead();
    }
    return false;
}

// In FIGHT decision:
if (isPlayerAlreadyInCombat()) {
    log.info("[FIGHT_SKIP] Player already in combat - not switching targets");
    break;  // Don't start new fight
}
```

## Key Files Changed

| File | Lines | Change |
|------|-------|--------|
| CombatSystem.java | 60 | Added `combatCommandActive` flag |
| CombatSystem.java | 1295-1308 | Getter/setter for flag |
| CombatSystem.java | 1643-1647 | Check flag in `onGameTick()` |
| CombatSystem.java | 1750-1772 | `isPlayerAlreadyInCombat()` helper |
| CombatSystem.java | 1823-1829 | Guard in FIGHT action |
| PlayerHelpers.java | 16836-16837 | Set flag at KILL_LOOP start |
| PlayerHelpers.java | 17383-17387 | Clear flag in finally block |

## When Autonomous Combat IS Useful

After the fix, autonomous combat serves its intended purpose as a **fallback defense**:

| Scenario | Autonomous Combat |
|----------|-------------------|
| AFK skilling, random aggro | ACTIVE - saves you from death |
| Traveling, attacked by mob | ACTIVE - handles without intervention |
| Running KILL_LOOP | SUPPRESSED - loop handles survival |
| Already fighting NPC_A, NPC_B attacks | SKIPS fight - finishes current target |

The decision logic (EAT at 50% HP, FLEE at 30% or if too strong, etc.) is genuinely useful for unexpected combat - just not when you're explicitly grinding.

## Pattern: Combat System Coordination

**BAD**: Relying on per-call flags (`manualCombatInProgress`) that leave gaps

**GOOD**: Command-level flags (`combatCommandActive`) that cover entire operation including side-effects

Future combat commands (KILL_COW, etc.) should also set `combatCommandActive` if they handle their own survival.
