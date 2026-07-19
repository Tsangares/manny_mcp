# 2026-07-19 — B3 ban-detection live gate: plugin-only path FAILS to fail-fast on a real banned account

**Author:** overseer session (post-window-#4 deploy). **Account:** `new` (GrimmsFairly, BANNED
2026-07-18), launched on display `:4` on diort against the freshly-deployed window-#4 jar
(`054d629…`, manny HEAD `2020530`). Zero ban risk (account already banned). The preserved
`newbakshesh` `:2` evidence client was never touched. Client torn down after ~1 min of observation.

## What the gate was supposed to prove

Runbook B3 / `BAN_DETECTION_REDESIGN_2026-07-19.md` §5: on an already-banned alias, the client
should **fail fast** — latch `terminal_login_failure` and STOP — **without** world-hopping through
5 worlds. Pass = a terminal signal surfaces (vision BANNED verdict and/or plugin latch), no hop storm.

## What actually happened (log evidence, `/tmp/runelite.log`, 10:00:08–10:00:59 PDT)

The plugin did **not** fail fast. It world-hopped and retried continuously:

- `loginIndex` **oscillates 10 ↔ 14** with `errorScreen=true` the entire window. `WorldSelector`
  hops worlds (`hopAttempts` climbs; `currentWorld` 306 → 436 → …); `TryAgainButtonClicker` clicks
  "try again" each cycle (10→14), which re-triggers a connect attempt (14→10).
- The hardened persistence heuristic **never latches**: it requires a *stable, same* non-{2,4}
  login index across consecutive observations to build a streak, but the index keeps flipping
  10↔14, so `streak` stays pinned at 1 and every sample logs `terminal=false`. The plugin's own
  world-hopping is what changes the index each cycle — **the WorldSelector defeats the streak
  detector** it's supposed to feed.
- State file `/tmp/manny_new_state.json`: `login` and `terminal_login_failure` are both **null**
  (login-state export not populated this run) and `player.location` is a **stale** pre-ban
  Lumbridge coord — so a driver polling *state* would also see no terminal signal.
- The intended **primary** detector per the redesign is **vision** (`analyze_screenshot` with the
  ban-classification prompt, driven by the Python `stuck_detector`/driver). A bare `mannyctl start`
  launches only the Java plugin, **not** the driver — so the vision path was **not exercised** here.

## The finding — DEFECT-32 (ban-detection)

**The plugin-signal-only path cannot stop a real banned account cleanly, and the streak-based
persistence backstop is specifically defeated by login-index oscillation.** Two sub-parts:

1. **Design-consistent part:** the redesign already concluded the ban message is rasterized and
   invisible to widget/reflection/`loginIndex`. So "plugin can't read *banned* from these signals"
   is expected — the answer was always vision. This gate *confirms* that: from `loginIndex` alone,
   "banned" is indistinguishable from a session/auth error (both are `errorScreen` cycling). (Note:
   `new`'s `jx_session_id` in `credentials.yaml` is shared with other aliases — a stale/shared token
   could itself produce generic error cycling, which only reinforces that `loginIndex` is not a
   trustworthy ban signal.)
2. **New part (the actual defect):** the persistence backstop added in `d553977`/`22247ce` assumed a
   banned account rests on a *stable* bad index. It doesn't here — the plugin's own retry/hop loop
   oscillates the index 10↔14, so the streak never accumulates and the backstop is dead code against
   this real case. Fix direction: treat *sustained `errorScreen` + N world-hops within a short
   window regardless of index stability* as terminal (hop-count/error-duration based), and/or gate
   world-hopping behind the terminal check so the client stops hopping instead of racing its own
   detector. And/or make the vision path the real gate (see below).

## Consequence / next step

The **vision path is the one that must actually be gated** — and it wasn't tested here because the
`manny-diort` MCP server (which exposes `analyze_screenshot`) was not connected in this session, and
a bare client launch doesn't run the Python ban chain. To finish B3 properly:

- Re-run against `new` **through the Python driver** (`mannyctl diort run <trivial-login-only
  routine> --account new`) so `stuck_detector` + the `analyze_screenshot` ban-classification path
  engages, OR with the `manny-diort` MCP connected so `analyze_screenshot` can be called directly on
  the `:4` framebuffer.
- Independently, file DEFECT-32 to make the plugin heuristic hop-count/duration based (not
  stable-index based) and/or stop world-hopping once a terminal-failure suspicion is raised.

B3 is therefore **NOT cleared** — the plugin-only path is a confirmed FAIL (world-hops, never
latches), and the intended vision path remains ungated. This does not block window-#4's other
value (the jar deploy itself is fine); it blocks *checking off* the ban-detection gate.
