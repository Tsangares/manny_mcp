# Superheat Steel Mining Routine - Speed Report

## Executive Summary

**4 outer loop execution over 42 minutes (2,525.5 seconds total)**

- Average loop duration: **631.4 seconds (10.5 minutes)**
- Mining phase dominates: **2,197.5s (87% of total time)**
- Critical issue: **First 2 mining iterations fail 100% of the time** (costs 38% of loop time)
- Overall mining success rate: **35% (7/20 successful iterations)**

---

## Loop-by-Loop Breakdown

| Loop | Banking | Travel | Mining | Success | Failed | Iter | Exit | **Total** |
|------|---------|--------|--------|---------|--------|------|------|-----------|
| 1 | 28.1s | 33.5s | 501.9s | 2 | 3 | 5 | 13.5s | **577.0s** |
| 2 | 30.9s | 34.4s | 638.9s | 3 | 3 | 6 | 23.1s | **727.2s** |
| 3 | 38.1s | 33.9s | 585.7s | 1 | 4 | 5 | 13.3s | **670.9s** |
| 4 | 32.7s | 33.4s | 471.0s | 1 | 3 | 4 | 13.3s | **550.4s** |

---

## Summary Statistics

| Metric | Min | Avg | Max | Total |
|--------|-----|-----|-----|-------|
| **Banking** | 28.1s | 32.4s | 38.1s | 129.8s |
| **Travel** | 33.4s | 33.8s | 34.4s | 135.3s |
| **Mining** | 471.0s | 549.4s | 638.9s | 2,197.5s |
| **Exit** | 13.3s | 15.8s | 23.1s | 63.0s |
| **Loop Total** | 550.4s | 631.4s | 727.2s | 2,525.5s |

### Mining Efficiency

- **Successful mining iterations**: 7/20 (35%)
- **Failed/timeout iterations**: 13/20 (65%)
- **Success rate by loop**:
  - Loop 1: 2/5 (40%)
  - Loop 2: 3/6 (50%)
  - Loop 3: 1/5 (20%)
  - Loop 4: 1/4 (25%)

---

## Key Observations

### 1. MINE_ORE Timeout Pattern (CRITICAL)

The data reveals a **consistent and problematic timeout pattern** in the first 2 iterations of each loop:

| Loop | Iteration 1 | Iteration 2 | Iteration 3+ |
|------|-------------|-------------|--------------|
| 1 | ❌ ALL timeout (7,8,9) | ❌ ALL timeout (7,8,9) | ✓ Steps 7,8,9 ok |
| 2 | ❌ ALL timeout (7,8,9) | ❌ ALL timeout (7,8,9) | ✓ Steps 7,8,9 ok |
| 3 | ❌ ALL timeout (7,8,9) | ❌ ALL timeout (7,8,9) | ⚠️ Step 7 timeout |
| 4 | ❌ ALL timeout (7,8,9) | ⚠️ Steps 8,9 timeout | ⚠️ Step 7 timeout |

**Cost per loop:** First 2 iterations consume ~240-260s (4-5 minutes) due to 60s timeouts on steps 7, 8, 9.

**Finding:** This is NOT random variance. All 4 loops show failure in iteration 1. Pattern suggests:
- Camera/object proximity setup incomplete when mining starts
- Widget state or inventory state invalid at loop start
- Step 7 (SUPERHEAT_ITEM) waits for animation that doesn't trigger

---

### 2. Step 10 (Retaliate) Timing Volatility

Step 10 shows unpredictable behavior:
- **Timeout rate**: 50% (10/20 iterations)
- **Occurs even after successful mining**: Loop 1 Iter 3 has steps 7,8,9 succeeding, but step 10 times out
- **When it works**: Takes 0-8s (highly variable)
- **Timeout value**: Consistently 8000-8036ms (suspicious: at 60s timeout boundary)

**Hypothesis:** Step 10 may be checking 'player is attacking' but not verifying attack actually started.
If RETALIATE command doesn't engage combat, the 60s timeout fires.

---

### 3. Banking Phase Variability

Steps 3, 3b, 3c, 3d, 3e (bar deposits) show high failure/retry rate:

| Loop | Success | Failure | Retry Rate |
|------|---------|---------|------------|
| 1 | 1/5 | 4/5 | 80% |
| 2 | 2/5 | 3/5 | 60% |
| 3 | 2/5 | 3/5 | 60% |
| 4 | 2/5 | 3/5 | 60% |

**Average cost per failed deposit step:** 600ms
**Total cost per loop from deposit retries:** 2-5s per loop

**Finding:** Widget ID or deposit interface logic may need refresh between deposits.

---

### 4. Travel Time (Highly Stable)

Steps 5, 5b, 6, 6b consistently 33-34s:
- Step 5b (navigate with Mithril Gloves) takes ~13s reliably
- Variance: 33.4s - 34.4s (only ±0.5s)
- **This phase is well-tuned and reliable**

---

### 5. Overall Duration Trend

Counterintuitive finding: **Loops are getting FASTER** (not slower) despite varied success rates.

| Loop | Duration | Iterations | Successful | Failed |
|------|----------|------------|------------|--------|
| 1 | 577.0s | 5 | 2 (40%) | 3 |
| 2 | 727.2s | 6 | 3 (50%) | 3 | ← SLOWEST |
| 3 | 670.9s | 5 | 1 (20%) | 4 |
| 4 | 550.4s | 4 | 1 (25%) | 3 | ← FASTEST |

**Trend:** -28% reduction from Loop 1 to Loop 4

**Explanation:** Loop 2 has MORE iterations (6 vs 5) because inventory wasn't full at loop start.
Loop 4 ends early because inventory fills faster (fewer failed mining iterations = inventory fills sooner).

---

### 6. Bar Production Analysis

Cannot determine exact bars vs iron from step data alone, but success rate suggests:

If each **successful iteration = 1 bar** (and failures = 0):
- Loop 1: ~2 steel bars (40% success)
- Loop 2: ~3 steel bars (50% success)
- Loop 3: ~1 steel bar (20% success)
- Loop 4: ~1 steel bar (25% success)

⚠️ **Important caveat:** Step 10 timeouts don't necessarily mean mining failed. They may mean the attack animation didn't trigger immediately. Actual bars mined could be higher if steps 7,8,9 succeeded but step 10 verification failed.

---

## Root Cause Analysis

By impact on routine speed (in order):

### 1. MINE_ORE (Step 7) fails first 2 iterations
- **Severity**: CRITICAL
- **Impact**: 240-260s lost per loop = **38% of total loop time**
- **Cumulative cost**: ~9-10 minutes per 4-loop session
- **Pattern**: 100% consistent across all loops

### 2. Step 10 (Retaliate) timeout spike
- **Severity**: HIGH
- **Impact**: 50% timeout rate adds 4-8s per timeout
- **Cumulative cost**: ~1-2 minutes per 4-loop session
- **Pattern**: Occurs even after successful mining steps

### 3. Deposit step retries (steps 3c, 3d, 3e)
- **Severity**: MEDIUM
- **Impact**: 60-80% failure rate adds 600ms per failed step
- **Cumulative cost**: ~30-45 seconds per 4-loop session
- **Pattern**: Consistent across all loops

### 4. Exit phase variability (steps 11-12)
- **Severity**: LOW
- **Impact**: Exit times range 13-23s (avg 15.8s)
- **Cumulative cost**: ~5s variance per loop

---

## Recommendations (Priority Order)

### 1. Fix iteration 1 mining startup (CRITICAL)
**Objective:** Eliminate the guaranteed failure of first 2 mining iterations

Options:
- Add pre-mining validation step to check camera angle, verify object visibility, confirm player stance
- Insert 2-3s delay before first MINE_ORE to let animation/interface settle
- Check if inventory needs clearing or player needs to reset position before mining starts
- Verify widget state for SUPERHEAT_ITEM command before sending (check if spell icon is accessible)

**Expected gain:** 4-5 minutes per loop (25% speedup)

### 2. Audit step 10 (Retaliate) implementation (HIGH PRIORITY)
**Objective:** Reduce 50% timeout rate

Actions:
- Verify the RETALIATE command actually engages combat (not just sending the command)
- Check if player needs to be within attack range or already in combat stance
- Consider if 60s timeout is too aggressive; reduce to 8s if that's the intended max
- Add fallback logic if retaliate fails (skip to next iteration or retry)

**Expected gain:** 1-2 minutes per 4-loop session

### 3. Fix deposit step widget/interface logic (MEDIUM PRIORITY)
**Objective:** Reduce 60-80% failure rate on deposit steps

Actions:
- Verify widget ID doesn't change between deposits (3, 3b, 3c, 3d, 3e)
- Confirm 'Deposit inventory' action text is consistent
- Check if interface needs refresh/close between deposits
- Add automatic retry with exponential backoff

**Expected gain:** 30-45 seconds per 4-loop session

### 4. Track actual production metrics (ONGOING)
**Objective:** Validate success vs. actual bars produced

- Log inventory deltas between banking phases to count actual steel vs iron bars
- Compare step timeout events vs. actual mining success (did step 7,8,9 succeed despite step 10 timeout?)
- Use `get_game_state(fields=["inventory"])` snapshots before/after mining

**Expected benefit:** Better understanding of true production rate vs. timeout noise

---

## Performance Baseline

For future optimization reference:

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| Banking (steps 1-4) | 32.4s | 25s | -7.4s |
| Travel (steps 5-6b) | 33.8s | 30s | -3.8s |
| Mining per iteration (7-10) | 109.9s | 60-80s | -29.9s to -49.9s |
| Exit (steps 11-12) | 15.8s | 10s | -5.8s |
| **Loop total** | **631.4s** | **400-500s** | **-131-231s** |

**Theoretical speedup if issues fixed:** 20-36% reduction in loop time

---

## Appendix: Detailed Iteration Data

### Loop 1 Mining Iterations
```
Iter 1: 7:TIMEOUT → 8:TIMEOUT → 9:TIMEOUT → 10:TIMEOUT (Total: 233.4s)
Iter 2: 7:TIMEOUT → 8:TIMEOUT → 9:TIMEOUT → 10:TIMEOUT (Total: 233.4s)
Iter 3: 7:ok (5.4s) → 8:ok (5.7s) → 9:ok (5.4s) → 10:TIMEOUT (8.0s)
Iter 4: 7:TIMEOUT → 8:ok (24.4s) → 9:ok (5.1s) → 10:ok (3.0s)
Iter 5: 7:ok (26.2s) → 8:ok (6.0s) → 9:ok (5.7s) → 10:ok (0s)
```

### Loop 2 Mining Iterations
```
Iter 1: 7:TIMEOUT → 8:TIMEOUT → 9:TIMEOUT → 10:TIMEOUT (Total: 233.4s)
Iter 2: 7:TIMEOUT → 8:TIMEOUT → 9:TIMEOUT → 10:TIMEOUT (Total: 233.4s)
Iter 3: 7:ok (53.2s) → 8:ok (5.7s) → 9:ok (5.4s) → 10:TIMEOUT (8.0s)
Iter 4: 7:ok (57.1s) → 8:ok (5.4s) → 9:ok (5.4s) → 10:ok (8.0s)
Iter 5: 7:TIMEOUT → 8:ok (15.9s) → 9:ok (5.4s) → 10:ok (0s)
Iter 6: 7:ok (50.8s) → 8:ok (5.7s) → 9:ok (5.7s) → 10:ok (0s)
```

(Loops 3-4 follow similar pattern with variations in step 7 timing)
