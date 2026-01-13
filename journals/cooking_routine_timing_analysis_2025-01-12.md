# Cooking Routine Timing Analysis - Lessons Learned
**Date:** 2025-01-12

## The Problem

The cooking_lumbridge.yaml routine needed timing benchmarks to identify optimization opportunities. Without timing data, it's impossible to know which phases are bottlenecks vs fixed delays.

## Root Cause

No prior systematic timing data existed for the routine. Each step's duration was unknown, making optimization guesswork.

## Timing Data Collected

Measured 4 full trips (112 lobsters) with manual step-by-step timing.

### Step-by-Step Timing (milliseconds)

| Step | Trip 1 | Trip 2 | Trip 3 | Trip 4 | Avg | Min | Max |
|------|--------|--------|--------|--------|-----|-----|-----|
| Banking (1-3) | N/A | 6500 | 10000* | 10000* | 8800 | 6500 | 10000 |
| GOTO stairs (4) | 8015 | 7517 | 7014 | 7517 | 7516 | 7014 | 8015 |
| Bottom-floor (5) | 2504 | 2004 | 2505 | 2505 | 2380 | 2004 | 2505 |
| GOTO range (6) | 6514 | 7015 | 6515 | 6515 | 6640 | 6514 | 7015 |
| Cook + Space (7-8) | ~2000 | ~2000 | ~2000 | ~2000 | 2000 | - | - |
| Cooking 28 (9) | 53120 | 53119 | 58129 | 58126 | 55624 | 53119 | 58129 |
| GOTO stairs (10) | 6514 | 6516 | 7515 | 8016 | 7140 | 6514 | 8016 |
| Top-floor (11) | 2506 | 5511 | 2505 | 2505 | 3257 | 2505 | 5511 |
| GOTO bank (12) | 7015 | 9019 | 7516 | 8018 | 7892 | 7015 | 9019 |
| Deposit (13-15) | 3000 | 3000 | 3000 | 3000 | 3000 | - | - |

*Trips 3-4 banking had interface timing issues requiring retry

### Phase Summary

| Phase | Time (ms) | % of Trip |
|-------|-----------|-----------|
| Banking | 8800 | 9% |
| Navigate Down | 9900 | 10% |
| Cooking Setup | 8640 | 9% |
| **Cooking (actual)** | **55624** | **57%** |
| Navigate Up | 18289 | 19% |
| Deposit | 3000 | 3% |
| **TOTAL** | **~97000** | 100% |

## Key Lessons

### 1. Cooking Time is Fixed - Cannot Be Optimized

**What happened:** Cooking 28 lobsters always takes 53-58 seconds
**Why:** Game tick rate (~600ms) x 28 items = 16.8 seconds minimum. Actual cooking animation adds more.
**Insight:** 57% of trip time is irreducible cooking animation. Focus optimization on the other 43%.

### 2. Bottom-floor/Top-floor is Fast (~2.5s) - Keep Using It

**What happened:** Staircase interactions using Bottom-floor/Top-floor consistently take 2-2.5 seconds
**Why:** Single click, instant plane change (skips middle floor entirely)
**Comparison:**
```yaml
# GOOD - Bottom-floor (2.5s)
action: INTERACT_OBJECT Staircase Bottom-floor
await_condition: plane:0

# BAD - Climb-down twice (5s+)
action: INTERACT_OBJECT Staircase Climb-down  # plane 2 -> 1
action: INTERACT_OBJECT Staircase Climb-down  # plane 1 -> 0
```

### 3. GOTO Navigation is the Biggest Variable (7-9s per segment)

**What happened:** GOTO commands show 2s variability (7-9 seconds)
**Why:** Pathing algorithm, player position variance, collision detection
**Potential optimization:** Pre-position player closer to objects before ending each phase

### 4. Interface Timing Causes Failures

**What happened:** Trip 3 banking failed because BANK_WITHDRAW was sent before BANK_OPEN completed
**Why:** BANK_OPEN was interrupted by the next command, leaving bank interface in unknown state
**Solution:**
```python
# BAD - sends withdraw too soon
send_command("BANK_OPEN")
sleep(2)  # Not enough!
send_command("BANK_WITHDRAW ...")  # May interrupt BANK_OPEN

# GOOD - wait for BANK_OPEN to fully complete
send_command("BANK_OPEN")
sleep(5)  # Allow camera prep + menu verification
send_command("BANK_WITHDRAW ...")
```

### 5. GOTO After Bank Close is Essential

**What happened:** Trip 4 GOTO failed with "stuck" error after closing bank
**Why:** Bank interface was still open (BANK_CLOSE hadn't completed)
**Solution:** Press Escape to ensure interfaces are closed before navigation
```python
# GOOD - ensure interface closed
send_command("BANK_CLOSE")
send_command("KEY_PRESS Escape")  # Safety
sleep(1)
send_command("GOTO ...")
```

## Anti-Patterns

1. **Don't send BANK_WITHDRAW immediately after BANK_OPEN** - BANK_OPEN takes 4-5 seconds (camera prep + menu verification)
2. **Don't send GOTO while bank interface is open** - Navigation commands fail with "stuck" error
3. **Don't use Climb-up/Climb-down** - Use Top-floor/Bottom-floor to skip middle floor (saves ~3-5s per trip)

## Optimization Opportunities

### High Impact (Easy)
1. **Reduce banking delay** - Current 5s wait could be 3s with better timing
2. **Add BANK_CLOSE verification** - Use await_condition to verify bank closed

### Medium Impact (Moderate)
1. **Optimize GOTO paths** - Current routes have variability; closer waypoints could help
2. **Pre-position for staircase** - End navigate-up closer to staircase to reduce next trip's navigate-down

### Low Impact (Already Optimized)
1. Cooking time - Fixed by game mechanics
2. Bottom-floor/Top-floor - Already using fastest method
3. KEY_PRESS Space - Already fast

## Theoretical Minimum Trip Time

| Phase | Optimized Time | Current | Savings |
|-------|---------------|---------|---------|
| Banking | 4000ms | 8800ms | 4800ms |
| Navigate Down | 8000ms | 9900ms | 1900ms |
| Cooking Setup | 7000ms | 8640ms | 1640ms |
| Cooking | 53000ms | 55624ms | 0ms* |
| Navigate Up | 14000ms | 18289ms | 4289ms |
| Deposit | 2000ms | 3000ms | 1000ms |
| **TOTAL** | **88s** | **97s** | **9s (9%)** |

*Cooking time variance is due to level-up dialogues, not inefficiency

## Results Summary

- **113 lobsters cooked** across 4+ trips
- **Cooking XP:** 189,940 -> 200,260 (+10,320 XP)
- **Success rate:** ~75-80% (some burnt at level 54-56)
- **Average trip time:** ~97 seconds for 28 lobsters
- **XP/hour estimate:** ~38,000 XP/hour

## Files Referenced

| File | Purpose |
|------|---------|
| `routines/skilling/cooking_lumbridge.yaml` | The routine being timed |
| `manny_src/utility/PlayerHelpers.java` | Command implementations |

## Interface Gaps Identified

- [ ] MCP needs: `await_bank_open` condition for more reliable banking
- [ ] Routine YAML needs: Better delay defaults between banking steps
- [ ] CLAUDE.md needs: Document banking timing requirements (5s minimum for BANK_OPEN)
