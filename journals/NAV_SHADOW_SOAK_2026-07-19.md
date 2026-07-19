# NAV-SHADOW Soak Report — 2026-07-19

Read-only analysis of `[NAV-SHADOW]` shadow-mode comparisons collected from diort
(`ShortestPathEngine` vs. legacy pathing). Data pulled from four sources on diort:
`/tmp/runelite_newbakshesh.log`, `/tmp/runelite_blast.log`, `~/.runelite/logs/client.log`
(current, mirrors the two per-account logs above — deduped), and the rotated
`~/.runelite/logs/client_2026-07-18.0.log` (prior session before the window-3 restart).
No `NAV-GRAPH` tag exists yet (0 hits everywhere); `NAV-EXACT` (53 hits in the rotated
log) is a separate exact-arrival hop mechanism, not the shadow comparator — noted but
not analyzed here.

## 1. Volume

| Source | Session window (PDT) | Account | Zone | Shadow lines |
|---|---|---|---|---|
| rotated `client_2026-07-18.0.log` | 21:31:33–22:35:45 | newbakshesh | tutorial-island/mainland boundary (x3122–3142) + Lumbridge mainland (x3221–3235) | 6 |
| `runelite_newbakshesh.log` (current) | 23:22:45–23:35:52 | newbakshesh | Lumbridge mainland, x3227–3235 y3291–3300 | 3 |
| `runelite_blast.log` (current) | 23:41:29–23:53:22 | blast | Tutorial island, x3072–3104 y3080–3120 | 13 |
| **Total (deduped)** | 21:31–23:53 (~2.4h span, two sessions) | both | mixed | **22** |

`client.log` (current, combined) shows 15 = 3(newbakshesh)+12(blast, at time of first
pull) confirming the two per-account logs and the shared framework log carry identical
events — no double-counting once deduped by source file.

**GOTO coverage:** `[GOTO] Executing command` totals: newbakshesh 3 (current) + 114
(rotated) = 117; blast 14 (current). Combined GOTO invocations = **131**. Shadow lines
fired for 22/131 ≈ **16.8%** of GOTO calls. The gap is likely explained by short hops
resolving through the separate `NAV-EXACT` exact-arrival snap path (53 instances in the
rotated log alone) rather than the shadow comparator — this is an assumption, not
confirmed from code; worth a one-line clarification from whoever owns
`NavigationHelpers` before relying on 16.8% as "true" coverage.

`ShortestPathEngine` load lines are consistent across every restart in this window:
`2724 regions with data (9078 slots), 595200 packed words (~4650 KB long[]), transports:
5168 edges (4708 free) from 5005 origin tiles; approx heap ~5.1 MB`, load time 148–197ms.
Same build, same graph data, across the rotated session and both current-session client
restarts — no engine drift.

## 2. graph=NONE rate

3 of 22 lines (13.6%) — **all three on tutorial island**, all from `blast`:

| Time | from | to | graphUs |
|---|---|---|---|
| 23:41:39 | (3098,3107,0) | (3100,3095,0) | 53,940 |
| 23:44:20 | (3073,3090,0) | (3072,3096,0) | 31,655 |
| 23:45:20 | (3074,3091,0) | (3072,3096,0) | 14,108 |

**Mainland NONE count: 0.** All 6 rotated-log lines and all 3 current-session
newbakshesh lines (pure Lumbridge mainland) resolved `graph=FOUND`. This matches the
known-acceptable-gap expectation: Skretzo collision data is understood to be thin on
tutorial island, so these three NONEs are a **flagged-benign gap**, not a mainland
collision-data hole. No serious NONEs observed in this soak.

## 3. Transport detection

**0 of 22 lines** show `transport>0`. Every FOUND line reports
`transport=0(doors=0,stairs=0)`. The soak so far has not exercised any route that
required a door or staircase, so there is currently **no observed evidence** of
graph-mode beating legacy via transport handling — the engine has 5168 transport edges
loaded, but none were hit by the sampled routes. This is a coverage gap for the WP5
"graph beats legacy" argument, not a negative result.

## 4. Performance (graphUs, all 22 samples)

| Stat | All 22 | FOUND-only (19) |
|---|---|---|
| Min | 100 µs | 100 µs |
| Median | 373 µs | 260 µs |
| Max | 58,012 µs | 58,012 µs |

Typical routes resolve in well under 1ms (median ~0.26–0.37ms), confirming the
sub-millisecond claim for normal-length paths. The tail is driven by two distinct
causes, not general slowness:
- The 3 `graph=NONE` cases (14.1ms–53.9ms) — expected, since NONE means the search
  exhausted the reachable space before giving up.
- One long FOUND route, steps=104 (rotated log, 22:10:00, (3221,3218,0)→(3235,3295,0),
  Lumbridge mainland), took 58.0ms — still fast in absolute terms but the outlier
  showing cost scales with route length/search-space size, not flat.

Excluding that one 104-step outlier, every other FOUND route (2–57 steps) completed in
≤4.6ms, mostly sub-millisecond.

## 5. Divergence

`firstDiverge=@0` on **all 19 FOUND lines, no exceptions** — including trivial 2-step
moves (rotated log, 21:31:50, (3122,3102,0)→(3122,3101,0), steps=2). This is worth
flagging as a pattern rather than dismissing: the task brief expected "early divergence
on long routes" to be normal, but here divergence at step 0 is universal regardless of
route length. Most plausible explanation is that `straight`/legacy's naive interpolated
first step differs from the collision-aware graph step even on short hops (e.g. avoiding
a single blocked tile) — consistent with graph being "more correct," not a bug — but a
100% @0 rate across all sampled data means this soak has not yet observed a case where
graph and legacy agree on the immediate first step. Not classified as anomalous, but
noted since it was unexpectedly uniform.

## 6. Verdict

**Not yet ready for a `graph`-mode live gate on mainland routes — soak is too thin, not
because of any observed defect.** In the data collected:

- Zero mainland `graph=NONE` events — good signal, no collision-data holes found on
  Lumbridge routes.
- Zero transport (`doors`/`stairs`) cases sampled — the strongest argument for
  graph-mode (routes legacy literally cannot solve) is **untested** in this window.
  WP5 should not claim a transport win without at least a handful of door/staircase
  crossings in shadow data.
- Performance looks solid: sub-millisecond typical, worst case 58ms on a 104-step route,
  still well within any reasonable timeout budget.
- Sample size is modest (22 shadow lines, 131 GOTO calls, ~16.8% shadow-instrumented)
  across only ~2.4 real hours split by a session restart. Mainland samples in
  particular are thin (9 total: 3 current-session newbakshesh + 6 rotated, all
  short-to-medium routes except the one 104-step outlier).

**Blockers for WP5 sign-off:**
1. No transport-path (door/stairs) shadow samples yet — need routes that cross at least
   one door/staircase to validate the graph's transport-beats-legacy case.
2. Mainland sample count is small; want more diverse mainland routes (different
   distances, more areas beyond the Lumbridge cluster seen here) before trusting the
   0%-NONE mainland rate as representative.
3. Clarify why only ~17% of GOTO calls produce a shadow line — confirm this is expected
   (NAV-EXACT short-hop bypass) rather than the shadow hook silently missing cases.

**Recommended extra soak:** let the current grind session run longer and re-collect once
shadow-line count is meaningfully higher (target 100+), ideally after a run that crosses
at least one door/staircase transport on the mainland, and after confirming the GOTO/
shadow coverage gap. Given today's data already clears the "≥10 lines" floor (22
collected), this report stands as a real baseline rather than a placeholder — but the
above three gaps should block the live-gate decision until closed.

---
*Collected read-only via SSH on diort; both `newbakshesh` (:2) and `blast` (:3) clients
were left untouched — no commands sent, no state files modified.*
