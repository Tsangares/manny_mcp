# 2026-07-19: Offline Verification + Adversarial Review

**Scope note:** this is the SECOND phase of 2026-07-19. The first phase (ban-pivot
response, money-maker audit fixes, corpus triage, the ban-detection redesign, the nav
integrity guard, and the first deploy-prep jar) is already written up in
`journals/2026-07-19_offline_hardening_day.md` (commit `6980310`) — not repeated here.
This entry covers what came after: building an offline verification pipeline for
routine correctness, running it, fixing what it found, then subjecting the whole day's
diff to an adversarial code review and hardening what that found. All of it stayed
offline — no client, no login, no remote host touched.

Repos: `manny_mcp` (`6980310..5ee78a2`), `manny` (`e56ba40..2020530`).

---

## 1. Why a verification pipeline, and what it's made of

Two things existed going into this phase: `validate_routine_deep` (static YAML
validation — schema, condition-grammar mixing, loop-schema mixing) and a
pathfinder collision harness (`manny` `PathfinderVerify`) checking generic
bridge/door/stair cases, not the actual routines. Neither answered "would this
routine get stuck live?" or "are these exact waypoints walkable?". Two new layers
closed that gap, offline, before anything touches a live account.

### Layer 2 — dynamic sequencing simulation (`mcptools/dryrun.py`)

`bd9c8c3` added `mcptools/dryrun.py`: an offline interpreter that steps a routine
through the *same* control flow `handle_execute_routine` uses (inner/outer + flat
loops, `on_failure`, `repeat`/`repeat_until`) against a scripted dict-based
`StateModel`, sending no command and touching no client. A small effect table
(`GOTO`→location, climbs→plane, `BANK_DEPOSIT_ALL`→empty inventory,
`KILL_LOOP_CONFIG`→configured batch) mutates the model; awaits are then checked by
reusing the engine's own condition parsers. It catches, pre-login: guaranteed-timeout
await/dialogue steps, condition-vocabulary mixing, blocking-command timeout traps,
loop-schema mixing, and silent step-failure march-on.

```bash
# Offline simulation -- safe pre-login, zero account risk
./run_routine.py routines/money_making/cowhide_banking.yaml --dry-run
./run_routine.py routines/money_making/chicken_feathers.yaml --dry-run --loops 2
```

Ships PASS end-to-end for both money-makers (cowhide ~6.3m simulated, feathers
~2.8h simulated) and all 11 tutorial_island routines. 17 tests added
(`tests/test_dryrun.py`).

`b1b55e2` then ran it across the *whole* corpus and found the failures were model
gaps, not real routine bugs: dialogue-advance commands were unmodeled for the item
they hand over (false-FAILed `restless_ghost` step 8 and `romeo_and_juliet` step 19),
gather commands didn't fill the inventory so an `inventory_full` inner-loop exit
never terminated (spun `mine_iron_ore` to the safety cap), ladders weren't modeled
like the Climb `INTERACT_OBJECT`, and unknown-command warnings fired on 24 cases
across 8 files that were really just unmodeled-but-real commands. Fixed all four;
corpus result: **39/39 executable routines PASS, 0 unknown-command warnings**,
dryrun tests at 317.

`c65f1de` fixed one more sequencing-fidelity gap: the simulator treated a failing
step inside an inner loop the same as any other step (march on to idx+1). Live
(`routine.py`) actually increments `inner_consecutive_failures` and *restarts* the
inner loop from `start_step`, falling through to `on_exit` after 3 consecutive
restarts. Mirrored that exactly so dry-run stops under-reporting how many times a
flaky inner-loop step gets retried before giving up. Test count moved to 324.

Documented in `ROUTINE_SCHEMA.md` §(k.1).

### Layer 3 — collision-map waypoint linter (`manny` `pathfinder/RouteLintVerify.java`)

Dry-run can't check whether a `GOTO`'s coordinates are actually walkable — that
requires the vendored collision/transport graph. `5590802` added
`RouteLintVerify`: it encodes the *actual* `cowhide_banking.yaml` and
`chicken_feathers.yaml` GOTO waypoint chains as ordered `(x,y,plane)` hops and
asserts each consecutive hop is pathable, within a sane length band (≤3× euclidean +
12 slack), and never dodges through the River Lum — plus a negative control (a
mid-river target must return no path) so the lint can't pass vacuously. Wired into
the refresh script:

```bash
cd /home/wil/Desktop/manny && \
  scripts/refresh_pathfinder_data.sh --apply --verify
```

`--verify` (requires `--apply`) compiles and runs all four harnesses —
`PathfinderVerify` + `NavShadowVerify` + `NavGraphVerify` + `RouteLintVerify` — after
applying vendored data, so a bad refresh reverts automatically rather than shipping.

`27dc5fa` extended the lint to the corpus routines the 07-19 fix pass touched
(`superheat_mining_guild`, `mining_falador_iron`, `hill_giants_restock/loot`,
`cow_killer_training`, `woodcutting_lumbridge`), adding an auto-classifier
(`lintCorpusChain`) that never edits a YAML and never hard-fails on a mere
free-transport-graph gap — it labels each finding `MISSING-REGION`, `KNOWN-BROKEN`
(non-walkable, skip + guard that flips to FAIL once fixed upstream), or
`UNREACHABLE-IN-FREE-GRAPH` (walkable but behind a keyed door absent from the
graph). `70fe060` synced the harness's Falador constants after the YAML-side repin
(§2 below).

---

## 2. The payoff: real bugs desk review missed

This is the point of building layers 2/3 — they found things a human re-reading the
YAML did not.

**Cowhide bridge + staircase pins (`5590802` finding, fixed `786c52e` /
`4536b91`).** The lint proved, against the vendored collision map, that
`cowhide_banking.yaml`'s bridge-hop waypoints (`3247,3228` / `3244,3227` /
`3239,3228`, steps 4/5/6 and the mirrored 21/22/23) sat *in the River Lum* — the
walkable bridge deck is `y<=3226`. Separately, the castle staircase base
`3205,3208` (steps 8/10/16/18) was blocked on all three planes; a 2026-07-18
desk-pass had actually moved it from the walkable `3205,3209` *onto* the blocked
tile. Both corrected in `manny_mcp` `786c52e` (bridge → `3247,3226`/`3244,3226`/
`3239,3226`, staircase → `3205,3209`); `manny` `4536b91` synced the harness
constants and dropped the skip-marks — **route-lint went from 33/33-with-6-skips to
71/71 with zero skips**, every hop in both routines now harness-verified walkable
and graph-connected in both directions.

**Mining Falador Iron — 3 more one-tile-off pins (`27dc5fa` finding, fixed
`manny_mcp` `87c3882` / `manny` `70fe060`).** The corpus sweep found
`mining_falador_iron.yaml` step-3 "inside building" (`3019,3450`), step-4 staircase
landing (`3019,9739`), and step-5 iron-rocks target (`3033,9737`) all one tile off
the vendored collision map's walkable surface. Repinned to the harness-confirmed
nearest walkable tile: `3018,3449` / `3018,9738` / `3032,9736`.

**Final route-lint state:** 116/116 checks, 1 legitimate skip — `hill_giants_restock`'s
brass-key door (`3115,3452`) is walkable but sits behind a keyed door absent from the
free-transport graph, a real transport-graph limitation, not a coordinate bug, so it
stays skip-marked rather than silenced.

**Dry-run corpus sweep:** 39/39 executable routines PASS, 0 real sequencing bugs
found (all findings were model gaps, fixed in `b1b55e2` per §1).

---

## 3. Adversarial review of the whole day's diff

With both layers green, the full day's diff across both repos got a read-only
adversarial review (both trees, no live testing — everything the day built was
reviewed for correctness, not just tested against its own fixtures).

**Result: 0 CONFIRMED bugs, 3 PLAUSIBLE false-latch paths** in the new
ban-*detection* heuristic — cases where a *healthy* login could get wrongly latched
as banned. All three were fixed:

- **Plugin-side stable-index streak (`manny` `d553977`).** The ban-persistence
  streak previously advanced on *any* non-{2,4} login index. Fixed two modes: (1)
  the streak now only advances when the *same* non-form index repeats on
  consecutive observations — mixed transient indices from normal connect churn no
  longer latch; (2) a streak inherited from a finished, unrelated login attempt is
  discarded — it restarts at 1 once the gap since the last observation exceeds 120s
  (well above the ~75s max within-cycle hop gap). Added `[LOGIN][SHADOW]
  index-sample` diagnostics logging every sampled index with context so the
  deferred live gate can empirically establish the real resting login-screen index.
- **Driver backstop hardening (`manny_mcp` `22247ce`).** The Python-side
  suspected-ban backstop fired on any non-{2,4} `login_index` held >30s, including
  transition indices that churn during a slow connect. Gated on index *stability*
  (timer resets on any index change) and widened the window 30s→120s, so a real ban
  screen (which parks on one index) still trips it but a slow legitimate connect
  doesn't. The plugin-latch path (`terminal_login_failure=true`) is untouched and
  still stops immediately. Also tightened `parse_vision_verdict` to require the
  verdict token as the exact leading word, so a reply like "not BANNED, it's NORMAL"
  no longer mislabels as BANNED. Test suite at 321.

Net effect: the backstop now requires either a stable unchanged login index held
≥120s, or the plugin's own hard latch — both harder to trip by accident, neither
weakened for a real ban.

**Two minor-note fixes** came out of the same review pass: `manny` `2020530` —
`ShortestPathEngine.getInstance()` wasn't caching a load failure, so every nav
`GOTO` after one failed load re-read ~1.5MB of vendored resources and recomputed
two sha256 digests, failing again each time (fixed with a volatile `initFailed`
sentinel); also a fingerprint key with an *empty* value (broken/half-written pin
file) was tripping the mismatch branch as if it were a real content mismatch, now
treated as a missing key (skip, WARN once). And `manny_mcp` `c65f1de` — the
dry-run inner-loop-restart fidelity fix from §1 (test count to 324).

---

## 4. Final artifact: the jar

The shaded jar was rebuilt clean at `manny` HEAD `2020530`, using the same
stash-before-build discipline as the first phase of the day (see below):
`runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar`, 40,095,064 bytes,
sha256 `054d629858dcc055982ff16eafab6a3f7cb0452f5de13b458876ed5555820e7b`. Spot-checked:
manny plugin classes present, pathfinder resources (`collision-map.zip`,
`transports/transports.tsv`, `data.fingerprint`) present, and the parked
`CameraDrift` class confirmed **absent** — parked code was not shipped. Recorded in
`journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md` blocker B4. Provisioning to diort
was NOT done — that's a live action gated on user approval (§5).

**One neutral note on scope:** both trees carry parked, user-owned edits unrelated
to this phase's work. They were kept out of every build and every commit this phase
touched via the same stash-before-build / scoped-commit discipline the first phase
established. Nothing about what they do is described here — that's out of this
session's scope by design.

---

## 5. Current open items

Everything left in the Track G sequence is now **live-gated on the user** — nothing
further is possible offline. In order:

1. **B1 — user decision on proxy/IP + account posture.** The standing blocker.
   Options on the table (routing through mat + the `dataimpulse` proxy, running on
   diort's already-flagged residential IP, or a fresh throwaway) and the account
   alias to use are both calls only the user can make. Nothing below unblocks until
   this is decided.
2. **Jar staging to diort.** Provision the `2020530` jar recorded in §4 once B1 is
   settled (`mannyctl diort provision`).
3. **Live gate #32 — zero-risk banned-alias login probe.** One login attempt on an
   *already-banned* alias, `STOP_PROCESSOR`, capture `[LOGIN]` logs + login game-state
   fields + a vision verdict, then stop. Risk is zero — a banned account cannot log
   in — but this is the gate that empirically confirms the hardened streak logic
   (§3) and captures the real resting login-screen index.
4. **Live gate #25 — DEFECT-21 bridge-crossing follower check.** Coordinates are
   now harness-proven walkable (§2); what remains live-only is the follower's actual
   click behavior on those tiles, crossed in both directions.
5. **Live gate #26 — attended cowhide cycles.** ≥2 consecutive
   kill→fill→bank→return cycles on `cowhide_banking.yaml`, attended, confirming the
   watchdog ledger shows genuine `running` progress and `active_loop` advances.
6. **Live gate #28 — Track G: 4+ hour unattended cowhide proof.** The capstone. Full
   preconditions, launch/monitor/abort procedure, and success criteria are in
   `journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md`.

No further offline verification work is queued — the pipeline (dry-run + route-lint)
is green across the full corpus and the day's diff has cleared adversarial review.
