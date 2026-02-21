# Routine Runner vs Manual Execution - Lessons Learned
**Date:** 2026-02-09

## The Problem

When asked to "continue the steel bars routine," the agent executed each mining/superheat step manually via individual `send_and_await` tool calls. This consumed thousands of tokens across ~60+ tool calls per trip, wasting context window and agent time on repetitive operations that `run_routine.py` handles automatically.

## Root Cause

1. **No CLAUDE.md guidance** mandating `run_routine.py` for routine execution. The Routine Execution Protocol section described how to follow YAML steps manually, not how to use the automated runner.
2. **Previous session context carried forward** - the prior conversation had been doing manual execution, and the continuation summary described the manual approach as the "current work."
3. **Agent defaulted to familiar pattern** - `send_and_await` is well-documented and comfortable; `run_routine.py` was not mentioned in any protocol section.

## Key Lessons

### 1. Always Use `run_routine.py` for YAML Routines

**What happened:** Agent manually called `send_and_await` ~120 times across 4 trips to execute what `run_routine.py` does in one command.
**Why:** No documented instruction to prefer the automated runner.
**Solution:**
```python
# BAD - manual step execution (wastes ~4 tool calls per cycle, ~100 per trip)
send_and_await("MINE_ORE coal 1", "inventory_count:>=3", timeout_ms=60000)
send_and_await("MINE_ORE coal 1", "inventory_count:>=4", timeout_ms=60000)
send_and_await("MINE_ORE iron 1", "has_item:Iron ore", timeout_ms=45000)
send_and_await("CAST_SPELL_ON_INVENTORY_ITEM Superheat_Item Iron_ore", "no_item:Iron ore", timeout_ms=8000)
# ... repeat 20+ times per trip

# GOOD - one command, runs autonomously with health checks and crash recovery
Bash("./run_routine.py routines/skilling/superheat_steel_bars.yaml --loops 10 --account main",
     run_in_background=True)
# Then monitor every 5-10 minutes with get_game_state()
```

### 2. `run_routine.py` Handles Edge Cases Automatically

**What happened:** During manual execution, the agent had to handle ghost coal buildup, adapt inventory count thresholds, retry failed mining, and manage banking deposits - all requiring agent judgment each time.
**Why:** The routine runner has built-in retry logic, inner/outer loop management, health checks every 5 steps, and crash auto-recovery (up to 3 restarts).
**Key features the manual approach lacked:**
- Automatic inner loop exit on `inventory_full`
- Retry with 2x timeout on failed `send_and_await`
- Health check + auto-restart on plugin freeze
- XP tracking across the full run

### 3. Deposit "Errors" Are Expected and Harmless

**What happened:** The routine runner reported 69 errors, ~60 of which were `BANK_DEPOSIT_ITEM` failures for items not in inventory (gems, iron bars, iron ore).
**Why:** The YAML routine defensively deposits all possible item types (steps 3b-3h). When those items aren't present, the command "fails" but the routine continues. This is correct behavior - deposit steps have no `await_condition` so failures don't block progression.
**Lesson:** Don't add `skip_if_missing` logic or try to optimize deposit steps. The defensive approach handles gem drops, ghost coal, and partial bars without needing conditional logic.

### 4. BANK_OPEN Failures Need a Delay or Proximity Check

**What happened:** 3 of 10 trips had `BANK_OPEN` fail, likely because the GOTO to bank arrived within 3 tiles but the character wasn't adjacent to a booth.
**Why:** `location:3012,3355` condition triggers within 3 tiles. BANK_OPEN requires being adjacent to a bank booth NPC/object. If the character stops 2-3 tiles away, BANK_OPEN can fail.
**Potential fix:** Add `delay_after_ms: 1000` to the GOTO step before BANK_OPEN, or use a closer coordinate. The routine runner retried and succeeded on subsequent attempts.

### 5. Ghost Coal Buildup Reduces Bars Per Trip

**What happened:** With 10 automated loops, the routine produced ~120 bars but carried 10-20+ ghost coal per trip, reducing effective bar count from ~24 to ~13-15 per trip.
**Why:** `MINE_ORE coal 1` sometimes yields extra coal (ghost mining bug - rock depletes mid-animation but ore is still added to inventory). Over a full trip of ~20 cycles, ghost coal accumulates because the inner loop doesn't account for extra coal already present.
**Impact:** ~40% fewer bars per trip than theoretical max. Coal gets deposited at bank so it doesn't compound across trips.
**Potential fix:** The inner loop could check actual coal count before mining and skip if >= 2, but this would require conditional step logic that the YAML format doesn't currently support.

## Anti-Patterns

1. **Don't manually execute YAML routine steps** - Use `run_routine.py`. Manual execution wastes thousands of tokens on repetitive tool calls and lacks retry/recovery logic.
2. **Don't panic about deposit errors** - `BANK_DEPOSIT_ITEM` for missing items is expected behavior in defensive deposit strategies.
3. **Don't assume the routine runner is broken from error count** - Check error types. 60/69 errors being "item not in inventory" is normal.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `./run_routine.py <yaml> --loops N --account main` | Run routine autonomously |
| `get_game_state(fields=["inventory", "location"])` | Quick progress check during run |
| `TaskOutput(task_id=..., block=False)` | Check if background routine is still running |
| `tail /tmp/claude-*/tasks/<id>.output` | Read routine output when complete |

## Interface Gaps Identified

- [ ] YAML routines lack conditional steps (e.g., "skip mining coal if already have 2")
- [ ] `BANK_OPEN` could benefit from an internal proximity walk before attempting to open
- [ ] Routine runner could suppress expected deposit failures from error count to reduce noise
- [ ] CLAUDE.md needed explicit `run_routine.py` mandate (now added)

## Files Modified

| File | Change |
|------|--------|
| `CLAUDE.md` | Rewrote "Routine Execution Protocol" section to mandate `run_routine.py` usage, document anti-patterns for manual execution, and add monitoring guidance |
